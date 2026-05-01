from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from nagient.app.configuration import AgentMemoryConfig
from nagient.domain.entities.memory import (
    MemorySearchResult,
    SessionMessage,
    SessionPromptContext,
)
from nagient.infrastructure.logging import RuntimeLogger
from nagient.workspace.manager import WorkspaceLayout


@dataclass
class SessionMemoryService:
    logger: RuntimeLogger

    def append_message(
        self,
        layout: WorkspaceLayout,
        *,
        session_id: str,
        transport_id: str,
        role: str,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> SessionMessage:
        normalized_content = content.strip()
        if not normalized_content:
            raise ValueError("Session memory cannot store an empty message.")
        with self._connect(layout) as connection:
            cursor = connection.execute(
                """
                INSERT INTO messages (
                    session_id,
                    transport_id,
                    role,
                    content,
                    created_at,
                    tokens_estimate,
                    in_focus,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    transport_id,
                    role,
                    normalized_content,
                    _utc_now(),
                    _estimate_tokens(normalized_content),
                    1,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            connection.commit()
            if cursor.lastrowid is None:
                raise ValueError("Failed to read the inserted message id from SQLite.")
            message_id = int(cursor.lastrowid)
            stored = self._message_by_id(connection, message_id)
        self.logger.info(
            "memory.append_message",
            "Stored session message.",
            workspace_id=layout.metadata.workspace_id,
            session_id=session_id,
            role=role,
            message_id=stored.message_id,
        )
        return stored

    def build_prompt_context(
        self,
        layout: WorkspaceLayout,
        *,
        session_id: str,
        config: AgentMemoryConfig,
        retrieval_query: str | None = None,
    ) -> SessionPromptContext:
        with self._connect(layout) as connection:
            self._sync_focus_flags(connection, session_id, config)
            connection.commit()
            all_messages = self._list_messages(connection, session_id)
            retrieved = (
                self._search_messages(
                    connection,
                    session_id=session_id,
                    query=retrieval_query,
                    limit=config.retrieval_max_results,
                )
                if retrieval_query
                else []
            )
        recent_messages = all_messages[-config.hard_message_limit :]
        if config.dynamic_focus_enabled:
            focus_messages = recent_messages[-config.dynamic_focus_messages :]
        else:
            focus_messages = list(recent_messages)
        archived_messages = all_messages[: max(0, len(all_messages) - len(recent_messages))]
        summary = (
            _summarize_messages(archived_messages)
            if len(archived_messages) >= config.summary_trigger_messages
            else ""
        )
        context = SessionPromptContext(
            session_id=session_id,
            summary=summary,
            recent_messages=recent_messages,
            focus_messages=focus_messages,
            retrieved_messages=retrieved,
        )
        self.logger.debug(
            "memory.build_prompt_context",
            "Built prompt context.",
            workspace_id=layout.metadata.workspace_id,
            session_id=session_id,
            recent_messages=len(recent_messages),
            focus_messages=len(focus_messages),
            retrieved_messages=len(retrieved),
        )
        return context

    def search_messages(
        self,
        layout: WorkspaceLayout,
        *,
        query: str,
        session_id: str | None = None,
        limit: int = 8,
    ) -> list[MemorySearchResult]:
        with self._connect(layout) as connection:
            results = self._search_messages(
                connection,
                session_id=session_id,
                query=query,
                limit=limit,
            )
        self.logger.info(
            "memory.search_messages",
            "Searched stored session messages.",
            workspace_id=layout.metadata.workspace_id,
            session_id=session_id or "*",
            query=query,
            results=len(results),
        )
        return results

    def create_note(
        self,
        layout: WorkspaceLayout,
        *,
        title: str,
        content: str,
        path_hint: str | None = None,
    ) -> Path:
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Note title must not be empty.")
        note_name = path_hint.strip() if path_hint else _slugify(normalized_title)
        note_path = _resolve_note_path(layout.notes_dir, note_name)
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(content, encoding="utf-8")
        self._index_note(layout, note_path, normalized_title, content)
        self.logger.info(
            "memory.create_note",
            "Created note file.",
            workspace_id=layout.metadata.workspace_id,
            note_path=note_path,
        )
        return note_path

    def update_note(
        self,
        layout: WorkspaceLayout,
        *,
        note_path: str,
        content: str,
    ) -> Path:
        path = _resolve_note_path(layout.notes_dir, note_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        title = _title_from_markdown(path.name, content)
        path.write_text(content, encoding="utf-8")
        self._index_note(layout, path, title, content)
        self.logger.info(
            "memory.update_note",
            "Updated note file.",
            workspace_id=layout.metadata.workspace_id,
            note_path=path,
        )
        return path

    def list_notes(self, layout: WorkspaceLayout) -> list[dict[str, object]]:
        self._refresh_notes_index(layout)
        notes: list[dict[str, object]] = []
        for path in sorted(layout.notes_dir.rglob("*.md")):
            notes.append(
                {
                    "path": str(path.relative_to(layout.notes_dir)),
                    "title": _title_from_markdown(path.name, path.read_text(encoding="utf-8")),
                    "updated_at": _iso_timestamp(path.stat().st_mtime),
                }
            )
        return notes

    def search_notes(
        self,
        layout: WorkspaceLayout,
        *,
        query: str,
        limit: int = 8,
    ) -> list[dict[str, object]]:
        self._refresh_notes_index(layout)
        with self._connect(layout) as connection:
            rows = connection.execute(
                """
                SELECT path, title, content, updated_at
                FROM notes
                WHERE title LIKE ? OR content LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        results: list[dict[str, object]] = [
            {
                "path": str(row["path"]),
                "title": str(row["title"]),
                "content": str(row["content"]),
                "updated_at": str(row["updated_at"]),
            }
            for row in rows
        ]
        self.logger.info(
            "memory.search_notes",
            "Searched indexed notes.",
            workspace_id=layout.metadata.workspace_id,
            query=query,
            results=len(results),
        )
        return results

    def _index_note(
        self,
        layout: WorkspaceLayout,
        path: Path,
        title: str,
        content: str,
    ) -> None:
        with self._connect(layout) as connection:
            connection.execute(
                """
                INSERT INTO notes (path, title, content, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    title = excluded.title,
                    content = excluded.content,
                    updated_at = excluded.updated_at
                """,
                (
                    str(path.relative_to(layout.notes_dir)),
                    title,
                    content,
                    _utc_now(),
                ),
            )
            connection.commit()

    def _refresh_notes_index(self, layout: WorkspaceLayout) -> None:
        if not layout.notes_dir.exists():
            return
        for path in sorted(layout.notes_dir.rglob("*.md")):
            content = path.read_text(encoding="utf-8")
            self._index_note(
                layout,
                path,
                _title_from_markdown(path.name, content),
                content,
            )

    def _connect(self, layout: WorkspaceLayout) -> sqlite3.Connection:
        db_path = layout.state_dir / "agent-state.sqlite3"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        self._ensure_schema(connection)
        return connection

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                transport_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                tokens_estimate INTEGER NOT NULL,
                in_focus INTEGER NOT NULL DEFAULT 1,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session_created
            ON messages(session_id, message_id);

            CREATE TABLE IF NOT EXISTS notes (
                path TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

    def _message_by_id(
        self,
        connection: sqlite3.Connection,
        message_id: int,
    ) -> SessionMessage:
        row = connection.execute(
            """
            SELECT message_id, session_id, transport_id, role, content, created_at,
                   tokens_estimate, in_focus, metadata_json
            FROM messages
            WHERE message_id = ?
            """,
            (message_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Stored message {message_id} was not found.")
        return _message_from_row(row)

    def _list_messages(
        self,
        connection: sqlite3.Connection,
        session_id: str,
    ) -> list[SessionMessage]:
        rows = connection.execute(
            """
            SELECT message_id, session_id, transport_id, role, content, created_at,
                   tokens_estimate, in_focus, metadata_json
            FROM messages
            WHERE session_id = ?
            ORDER BY message_id ASC
            """,
            (session_id,),
        ).fetchall()
        return [_message_from_row(row) for row in rows]

    def _search_messages(
        self,
        connection: sqlite3.Connection,
        *,
        query: str,
        limit: int,
        session_id: str | None,
    ) -> list[MemorySearchResult]:
        normalized_limit = max(1, limit)
        parameters: list[object] = [f"%{query}%"]
        sql = """
            SELECT message_id, session_id, role, content, created_at
            FROM messages
            WHERE content LIKE ?
        """
        if session_id is not None:
            sql += " AND session_id = ?"
            parameters.append(session_id)
        sql += " ORDER BY message_id DESC LIMIT ?"
        parameters.append(normalized_limit)
        rows = connection.execute(sql, tuple(parameters)).fetchall()
        return [
            MemorySearchResult(
                message_id=int(row["message_id"]),
                session_id=str(row["session_id"]),
                role=str(row["role"]),
                content=str(row["content"]),
                created_at=str(row["created_at"]),
                score=1.0,
            )
            for row in rows
        ]

    def _sync_focus_flags(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        config: AgentMemoryConfig,
    ) -> None:
        focus_limit = (
            config.dynamic_focus_messages
            if config.dynamic_focus_enabled
            else config.hard_message_limit
        )
        rows = connection.execute(
            """
            SELECT message_id
            FROM messages
            WHERE session_id = ?
            ORDER BY message_id DESC
            LIMIT ?
            """,
            (session_id, focus_limit),
        ).fetchall()
        focus_ids = {int(row["message_id"]) for row in rows}
        connection.execute(
            "UPDATE messages SET in_focus = 0 WHERE session_id = ?",
            (session_id,),
        )
        for message_id in focus_ids:
            connection.execute(
                "UPDATE messages SET in_focus = 1 WHERE message_id = ?",
                (message_id,),
            )


def _message_from_row(row: sqlite3.Row) -> SessionMessage:
    metadata_payload = row["metadata_json"]
    metadata: dict[str, object] = {}
    if isinstance(metadata_payload, str):
        try:
            parsed = json.loads(metadata_payload)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            metadata = {str(key): value for key, value in parsed.items()}
    return SessionMessage(
        message_id=int(row["message_id"]),
        session_id=str(row["session_id"]),
        transport_id=str(row["transport_id"]),
        role=str(row["role"]),
        content=str(row["content"]),
        created_at=str(row["created_at"]),
        tokens_estimate=int(row["tokens_estimate"]),
        in_focus=bool(row["in_focus"]),
        metadata=metadata,
    )


def _estimate_tokens(content: str) -> int:
    return max(1, len(content.encode("utf-8")) // 4)


def _summarize_messages(messages: list[SessionMessage]) -> str:
    if not messages:
        return ""
    lines: list[str] = []
    for message in messages[-20:]:
        content = message.content.replace("\n", " ").strip()
        if len(content) > 180:
            content = content[:177] + "..."
        lines.append(f"{message.role}: {content}")
    return "\n".join(lines)


def _slugify(value: str) -> str:
    normalized = "".join(
        char.lower() if char.isalnum() else "-" for char in value.strip()
    )
    collapsed = "-".join(part for part in normalized.split("-") if part)
    return collapsed or f"note-{int(time.time())}"


def _resolve_note_path(notes_dir: Path, note_path: str) -> Path:
    candidate = (notes_dir / note_path).resolve()
    if candidate.suffix.lower() != ".md":
        candidate = candidate.with_suffix(".md")
    if not candidate.is_relative_to(notes_dir.resolve()):
        raise PermissionError("Note path is outside the notes directory.")
    return candidate


def _title_from_markdown(file_name: str, content: str) -> str:
    for line in content.splitlines():
        normalized = line.strip()
        if normalized.startswith("#"):
            return normalized.lstrip("#").strip() or file_name.rsplit(".", 1)[0]
    return file_name.rsplit(".", 1)[0]


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _iso_timestamp(raw_timestamp: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(raw_timestamp))
