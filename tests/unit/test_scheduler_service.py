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
            self.assertEqual(service.list_jobs(layout), [])

    def test_schedule_once_normalizes_relative_run_at(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings.from_env({"NAGIENT_HOME": str(Path(temp_dir) / "home")})
            layout = WorkspaceManager(settings).ensure_layout(
                WorkspaceConfig(root=Path(temp_dir) / "workspace", mode="bounded")
            )
            service = SchedulerService(RuntimeLogger(settings, "scheduler-test"))

            job = service.schedule_once(
                layout,
                run_at="in 10 seconds",
                payload={"action_type": "agent.wake", "message": "hello"},
                name="wake",
            )

            self.assertRegex(job.run_at or "", r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            self.assertNotEqual(job.run_at, "in 10 seconds")
            next_due = service.seconds_until_next_due(layout)
            self.assertIsNotNone(next_due)
            self.assertLessEqual(next_due or 999, 10)

    def test_cancel_interval_job_updates_status(self) -> None:
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

    def test_cancel_once_job_deletes_stored_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings.from_env({"NAGIENT_HOME": str(Path(temp_dir) / "home")})
            layout = WorkspaceManager(settings).ensure_layout(
                WorkspaceConfig(root=Path(temp_dir) / "workspace", mode="bounded")
            )
            service = SchedulerService(RuntimeLogger(settings, "scheduler-test"))
            job = service.schedule_once(
                layout,
                run_at="in 60 seconds",
                payload={"action_type": "agent.wake", "message": "tick"},
                name="once",
            )

            cancelled = service.cancel_job(layout, job.job_id)

            self.assertEqual(cancelled.status, "cancelled")
            self.assertEqual(service.list_jobs(layout), [])


if __name__ == "__main__":
    unittest.main()
