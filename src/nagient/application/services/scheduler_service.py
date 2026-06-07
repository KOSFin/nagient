from __future__ import annotations

import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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
        normalized_run_at = normalize_run_at(run_at)
        job = JobRecord(
            job_id=_job_id(),
            name=name,
            status="scheduled",
            trigger="once",
            created_at=_utc_now(),
            run_at=normalized_run_at,
            payload=dict(payload),
            notes=notes,
        )
        self._store(layout).save(job)
        self.logger.info(
            "scheduler.schedule_once",
            "Scheduled one-off job.",
            workspace_id=layout.metadata.workspace_id,
            job_id=job.job_id,
            run_at=normalized_run_at,
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
            try:
                handler(job)
            except Exception as exc:
                failed = JobRecord(
                    job_id=job.job_id,
                    name=job.name,
                    status="failed",
                    trigger=job.trigger,
                    created_at=job.created_at,
                    run_at=job.run_at,
                    interval_seconds=job.interval_seconds,
                    event_name=job.event_name,
                    payload=job.payload,
                    last_run_at=_utc_now(),
                    notes=_append_job_note(job.notes, f"Last error: {exc}"),
                )
                store.save(failed)
                self.logger.error(
                    "scheduler.run_due_job_failed",
                    "Scheduled job failed.",
                    workspace_id=layout.metadata.workspace_id,
                    job_id=job.job_id,
                    trigger=job.trigger,
                    error=str(exc),
                )
                continue
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

    def seconds_until_next_due(self, layout: WorkspaceLayout) -> float | None:
        return self._store(layout).seconds_until_next_due()

    def _store(self, layout: WorkspaceLayout) -> JobStore:
        return JobStore(layout.jobs_dir)


def _job_id() -> str:
    return f"job_{uuid.uuid4().hex[:16]}"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_run_at(value: str, *, now: datetime | None = None) -> str:
    parsed = _parse_run_at(value, now=now)
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def run_at_after(delay_seconds: int, *, now: datetime | None = None) -> str:
    if delay_seconds <= 0:
        raise ValueError("delay_seconds must be a positive integer.")
    current = now or datetime.now(tz=UTC)
    return (current + timedelta(seconds=delay_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_run_at(value: str, *, now: datetime | None = None) -> datetime:
    raw = value.strip()
    if not raw:
        raise ValueError("run_at must not be empty.")
    relative_seconds = _relative_seconds(raw)
    if relative_seconds is not None:
        current = now or datetime.now(tz=UTC)
        return current + timedelta(seconds=relative_seconds)
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            "run_at must be an ISO timestamp like 2026-06-07T13:30:00Z "
            "or a relative delay like 'in 10 seconds'."
        ) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _relative_seconds(value: str) -> int | None:
    normalized = value.strip().lower()
    match = re.fullmatch(
        r"(?:in\s+)?(?P<count>\d+)\s*(?P<unit>s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hour|hours)",
        normalized,
    )
    if not match:
        return None
    count = int(match.group("count"))
    unit = match.group("unit")
    if unit.startswith("s"):
        return count
    if unit.startswith("m"):
        return count * 60
    if unit.startswith("h"):
        return count * 3600
    return None


def _append_job_note(notes: str | None, extra: str) -> str:
    if not notes:
        return extra
    return f"{notes}\n{extra}"
