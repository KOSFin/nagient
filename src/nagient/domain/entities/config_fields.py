from __future__ import annotations

from dataclasses import dataclass

_ALLOWED_CONFIG_FIELD_TYPES = {
    "string",
    "integer",
    "number",
    "boolean",
    "json",
    "path",
    "secret",
}
_ALLOWED_CONFIG_FIELD_CATEGORIES = {
    "connection",
    "advanced",
    "general",
}


@dataclass(frozen=True)
class ConfigFieldSpec:
    key: str
    label: str = ""
    help_text: str = ""
    value_type: str = "string"
    category: str = "advanced"
    required: bool = False
    secret: bool = False

    def normalized_value_type(self) -> str:
        normalized = self.value_type.strip().lower().replace("-", "_")
        if normalized in _ALLOWED_CONFIG_FIELD_TYPES:
            return normalized
        return "string"

    def normalized_category(self) -> str:
        normalized = self.category.strip().lower()
        if normalized in _ALLOWED_CONFIG_FIELD_CATEGORIES:
            return normalized
        return "advanced"

    def display_label(self) -> str:
        return self.label.strip() or self.key

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "help_text": self.help_text,
            "value_type": self.normalized_value_type(),
            "category": self.normalized_category(),
            "required": self.required,
            "secret": self.secret,
        }
