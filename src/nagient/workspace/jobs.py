from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from nagient.domain.entities.jobs import JobRecord


@dataclass(frozen=True)
class JobStore:
    jobs_dir: Path

    def save(self, job: JobRecord) -> Path:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        path = self.jobs_dir / f"{job.job_id}.json"
        path.write_text(json.dumps(job.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path

    def load(self, job_id: str) -> JobRecord | None:
        path = self.jobs_dir / f"{job_id}.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        return JobRecord.from_dict(payload)

    def list(self) -> list[JobRecord]:
        if not self.jobs_dir.exists():
            return []
        jobs: list[JobRecord] = []
        for path in sorted(self.jobs_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                jobs.append(JobRecord.from_dict(payload))
        return jobs

    def due(self, now: datetime | None = None) -> list[JobRecord]:
        current = now or datetime.now(tz=timezone.utc)
        due_jobs: list[JobRecord] = []
        for job in self.list():
            if job.status not in {"pending", "scheduled"}:
                continue
            if job.trigger == "event":
                continue
            if job.trigger == "once" and job.run_at and _parse_time(job.run_at) <= current:
                due_jobs.append(job)
                continue
            if job.trigger == "interval" and job.interval_seconds is not None:
                last_run = _parse_time(job.last_run_at) if job.last_run_at else None
                if last_run is None or (current - last_run).total_seconds() >= job.interval_seconds:
                    due_jobs.append(job)
        return due_jobs


def _parse_time(value: str | None) -> datetime:
    if value is None:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
