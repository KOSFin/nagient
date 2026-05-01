from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nagient.app.configuration import WorkspaceConfig
from nagient.app.settings import Settings
from nagient.application.services.scheduler_service import SchedulerService
from nagient.infrastructure.logging import RuntimeLogger
from nagient.workspace.manager import WorkspaceManager


class SchedulerServiceTests(unittest.TestCase):
    def test_schedule_and_run_due_job(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings.from_env({"NAGIENT_HOME": str(Path(temp_dir) / "home")})
            layout = WorkspaceManager(settings).ensure_layout(
                WorkspaceConfig(root=Path(temp_dir) / "workspace", mode="bounded")
            )
            service = SchedulerService(RuntimeLogger(settings, "scheduler-test"))
            run_at = (datetime.now(tz=UTC) - timedelta(minutes=1)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            job = service.schedule_once(
                layout,
                run_at=run_at,
                payload={"action_type": "agent.wake", "message": "hello"},
                name="wake",
            )

            seen: list[str] = []
            executed = service.run_due_jobs(
                layout,
                lambda current_job: seen.append(current_job.job_id),
            )

            self.assertEqual(seen, [job.job_id])
            self.assertEqual(len(executed), 1)
            self.assertEqual(executed[0].status, "completed")

    def test_cancel_job_updates_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings.from_env({"NAGIENT_HOME": str(Path(temp_dir) / "home")})
            layout = WorkspaceManager(settings).ensure_layout(
                WorkspaceConfig(root=Path(temp_dir) / "workspace", mode="bounded")
            )
            service = SchedulerService(RuntimeLogger(settings, "scheduler-test"))
            job = service.schedule_interval(
                layout,
                interval_seconds=60,
                payload={"action_type": "agent.wake", "message": "tick"},
                name="interval",
            )

            cancelled = service.cancel_job(layout, job.job_id)

            self.assertEqual(cancelled.status, "cancelled")


if __name__ == "__main__":
    unittest.main()
