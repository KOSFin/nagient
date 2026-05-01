from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SessionMessage:
    message_id: int
    session_id: str
    transport_id: str
    role: str
    content: str
    created_at: str
    tokens_estimate: int
    in_focus: bool
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "transport_id": self.transport_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "tokens_estimate": self.tokens_estimate,
            "in_focus": self.in_focus,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MemorySearchResult:
    message_id: int
    session_id: str
    role: str
    content: str
    created_at: str
    score: float

    def to_dict(self) -> dict[str, object]:
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "score": self.score,
        }


@dataclass(frozen=True)
class SessionPromptContext:
    session_id: str
    summary: str
    recent_messages: list[SessionMessage] = field(default_factory=list)
    focus_messages: list[SessionMessage] = field(default_factory=list)
    retrieved_messages: list[MemorySearchResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "summary": self.summary,
            "recent_messages": [message.to_dict() for message in self.recent_messages],
            "focus_messages": [message.to_dict() for message in self.focus_messages],
            "retrieved_messages": [
                message.to_dict() for message in self.retrieved_messages
            ],
        }
