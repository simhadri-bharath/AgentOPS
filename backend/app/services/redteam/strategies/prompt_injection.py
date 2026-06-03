"""Prompt injection attack strategy."""

from app.services.redteam.library_loader import library_to_attack_cases
from app.services.redteam.strategies.base import AttackCase, RedTeamStrategy


class PromptInjectionStrategy(RedTeamStrategy):
    category = "prompt_injection"

    def load_cases(self, *, enabled_only: bool = True) -> list[AttackCase]:
        return library_to_attack_cases(self.category, enabled_only=enabled_only)
