from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from nagient.domain.entities.jobs import JobRecord
from nagient.infrastructure.logging import RuntimeLogger
from nagient.workspace.jobs import JobStore
from nagient.workspace.manager import WorkspaceLayout


@dataclass
class SchedulerService:
    logger: RuntimeLogger

    def schedule_once(
        self,
        layout: WorkspaceLayout,
        *,
        run_at: str,
        payload: dict[str, object],
        name: str,
        notes: str | None = None,
    ) -> JobRecord:
        job = JobRecord(
            job_id=_job_id(),
            name=name,
            status="scheduled",
            trigger="once",
            created_at=_utc_now(),
            run_at=run_at,
            payload=dict(payload),
            notes=notes,
        )
        self._store(layout).save(job)
        self.logger.info(
            "scheduler.schedule_once",
            "Scheduled one-off job.",
            workspace_id=layout.metadata.workspace_id,
            job_id=job.job_id,
            run_at=run_at,
            name=name,
        )
        return job

    def schedule_interval(
        self,
        layout: WorkspaceLayout,
        *,
        interval_seconds: int,
        payload: dict[str, object],
        name: str,
        notes: str | None = None,
    ) -> JobRecord:
        if interval_seconds <= 0:
            raise ValueError("Interval job requires a positive interval_seconds.")
        job = JobRecord(
            job_id=_job_id(),
            name=name,
            status="scheduled",
            trigger="interval",
            created_at=_utc_now(),
            interval_seconds=interval_seconds,
            payload=dict(payload),
            notes=notes,
        )
        self._store(layout).save(job)
        self.logger.info(
            "scheduler.schedule_interval",
            "Scheduled interval job.",
            workspace_id=layout.metadata.workspace_id,
            job_id=job.job_id,
            interval_seconds=interval_seconds,
            name=name,
        )
        return job

    def list_jobs(self, layout: WorkspaceLayout) -> list[JobRecord]:
        jobs = self._store(layout).list()
        self.logger.debug(
            "scheduler.list_jobs",
            "Listed stored jobs.",
            workspace_id=layout.metadata.workspace_id,
            jobs=len(jobs),
        )
        return jobs

    def cancel_job(
        self,
        layout: WorkspaceLayout,
        job_id: str,
    ) -> JobRecord:
        job = self._store(layout).load(job_id)
        if job is None:
            raise ValueError(f"Job {job_id!r} was not found.")
        cancelled = JobRecord(
            job_id=job.job_id,
            name=job.name,
            status="cancelled",
            trigger=job.trigger,
            created_at=job.created_at,
            run_at=job.run_at,
            interval_seconds=job.interval_seconds,
            event_name=job.event_name,
            payload=job.payload,
            last_run_at=job.last_run_at,
            notes=job.notes,
        )
        self._store(layout).save(cancelled)
        self.logger.info(
            "scheduler.cancel_job",
            "Cancelled scheduled job.",
            workspace_id=layout.metadata.workspace_id,
            job_id=job_id,
        )
        return cancelled

    def run_due_jobs(
        self,
        layout: WorkspaceLayout,
        handler: Callable[[JobRecord], None],
    ) -> list[JobRecord]:
        store = self._store(layout)
        due_jobs = store.due()
        executed: list[JobRecord] = []
        for job in due_jobs:
            handler(job)
            updated = JobRecord(
                job_id=job.job_id,
                name=job.name,
                status="completed" if job.trigger == "once" else "scheduled",
                trigger=job.trigger,
                created_at=job.created_at,
                run_at=job.run_at,
                interval_seconds=job.interval_seconds,
                event_name=job.event_name,
                payload=job.payload,
                last_run_at=_utc_now(),
                notes=job.notes,
            )
            store.save(updated)
            executed.append(updated)
            self.logger.info(
                "scheduler.run_due_job",
                "Executed due job.",
                workspace_id=layout.metadata.workspace_id,
                job_id=job.job_id,
                trigger=job.trigger,
            )
        return executed

    def _store(self, layout: WorkspaceLayout) -> JobStore:
        return JobStore(layout.jobs_dir)


def _job_id() -> str:
    return f"job_{uuid.uuid4().hex[:16]}"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
