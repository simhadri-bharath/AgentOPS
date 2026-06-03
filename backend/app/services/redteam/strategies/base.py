"""Base red team attack strategy (plugin interface)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AttackCase:
    """Normalized attack test case for execution."""

    id: str
    category: str
    severity: str
    prompt: str
    expected_behavior: str
    tags: list[str] = field(default_factory=list)
    source: str = "library"
    db_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class RedTeamStrategy(ABC):
    """Pluggable attack category strategy (DeepTeam / Promptfoo / Garak compatible shape)."""

    category: str

    @abstractmethod
    def load_cases(self, *, enabled_only: bool = True) -> list[AttackCase]:
        """Load built-in library cases for this category."""

    @property
    def framework_id(self) -> str:
        return f"agentops_{self.category}"
