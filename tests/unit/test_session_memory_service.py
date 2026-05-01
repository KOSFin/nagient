from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.app.configuration import AgentMemoryConfig, WorkspaceConfig
from nagient.app.settings import Settings
from nagient.application.services.session_memory_service import SessionMemoryService
from nagient.infrastructure.logging import RuntimeLogger
from nagient.workspace.manager import WorkspaceManager


class SessionMemoryServiceTests(unittest.TestCase):
    def test_prompt_context_applies_hard_limit_and_focus_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings.from_env({"NAGIENT_HOME": str(Path(temp_dir) / "home")})
            layout = WorkspaceManager(settings).ensure_layout(
                WorkspaceConfig(root=Path(temp_dir) / "workspace", mode="bounded")
            )
            service = SessionMemoryService(RuntimeLogger(settings, "memory-test"))

            for index in range(6):
                service.append_message(
                    layout,
                    session_id="session-1",
                    transport_id="console",
                    role="user" if index % 2 == 0 else "assistant",
                    content=f"message {index}",
                )

            context = service.build_prompt_context(
                layout,
                session_id="session-1",
                config=AgentMemoryConfig(
                    hard_message_limit=4,
                    dynamic_focus_enabled=True,
                    dynamic_focus_messages=2,
                    summary_trigger_messages=2,
                    retrieval_max_results=4,
                ),
            )

            self.assertEqual(len(context.recent_messages), 4)
            self.assertEqual(len(context.focus_messages), 2)
            self.assertIn("message 0", context.summary)
            self.assertEqual(context.focus_messages[-1].content, "message 5")

    def test_notes_are_created_and_searchable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings.from_env({"NAGIENT_HOME": str(Path(temp_dir) / "home")})
            layout = WorkspaceManager(settings).ensure_layout(
                WorkspaceConfig(root=Path(temp_dir) / "workspace", mode="bounded")
            )
            service = SessionMemoryService(RuntimeLogger(settings, "memory-test"))

            note_path = service.create_note(
                layout,
                title="Release Checklist",
                content="# Release Checklist\n\nShip Telegram typing support.",
            )
            results = service.search_notes(layout, query="Telegram", limit=4)

            self.assertTrue(note_path.exists())
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["title"], "Release Checklist")

    def test_existing_nested_notes_are_indexed_and_listed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings.from_env({"NAGIENT_HOME": str(Path(temp_dir) / "home")})
            layout = WorkspaceManager(settings).ensure_layout(
                WorkspaceConfig(root=Path(temp_dir) / "workspace", mode="bounded")
            )
            service = SessionMemoryService(RuntimeLogger(settings, "memory-test"))
            note_path = layout.notes_dir / "plans" / "next-step.md"
            note_path.parent.mkdir(parents=True, exist_ok=True)
            note_path.write_text("# Next Step\n\nCheck Telegram callbacks.", encoding="utf-8")

            notes = service.list_notes(layout)
            results = service.search_notes(layout, query="callbacks", limit=4)

            self.assertEqual(notes[0]["path"], "plans/next-step.md")
            self.assertEqual(results[0]["path"], "plans/next-step.md")


if __name__ == "__main__":
    unittest.main()
