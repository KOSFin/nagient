from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    name: str
    status: str
    trigger: str
    created_at: str
    run_at: str | None = None
    interval_seconds: int | None = None
    event_name: str | None = None
    payload: dict[str, object] = field(default_factory=dict)
    last_run_at: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "job_id": self.job_id,
            "name": self.name,
            "status": self.status,
            "trigger": self.trigger,
            "created_at": self.created_at,
            "payload": dict(self.payload),
        }
        if self.run_at is not None:
            payload["run_at"] = self.run_at
        if self.interval_seconds is not None:
            payload["interval_seconds"] = self.interval_seconds
        if self.event_name is not None:
            payload["event_name"] = self.event_name
        if self.last_run_at is not None:
            payload["last_run_at"] = self.last_run_at
        if self.notes is not None:
            payload["notes"] = self.notes
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> JobRecord:
        interval_seconds = payload.get("interval_seconds")
        return cls(
            job_id=str(payload.get("job_id", "")),
            name=str(payload.get("name", "")),
            status=str(payload.get("status", "pending")),
            trigger=str(payload.get("trigger", "once")),
            created_at=str(payload.get("created_at", "")),
            run_at=str(payload["run_at"]) if "run_at" in payload else None,
            interval_seconds=(
                int(interval_seconds) if isinstance(interval_seconds, int) else None
            ),
            event_name=str(payload["event_name"]) if "event_name" in payload else None,
            payload=dict(payload.get("payload", {}))
            if isinstance(payload.get("payload"), dict)
            else {},
            last_run_at=(
                str(payload["last_run_at"]) if "last_run_at" in payload else None
            ),
            notes=str(payload["notes"]) if "notes" in payload else None,
        )
