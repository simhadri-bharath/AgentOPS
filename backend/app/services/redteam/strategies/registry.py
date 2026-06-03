"""Strategy registry for pluggable red team frameworks."""

from __future__ import annotations

from app.services.redteam.strategies.base import AttackCase, RedTeamStrategy
from app.services.redteam.strategies.boundary import BoundaryStrategy
from app.services.redteam.strategies.jailbreak import JailbreakStrategy
from app.services.redteam.strategies.pii_extraction import PiiExtractionStrategy
from app.services.redteam.strategies.prompt_injection import PromptInjectionStrategy

STRATEGY_REGISTRY: dict[str, type[RedTeamStrategy]] = {
    "prompt_injection": PromptInjectionStrategy,
    "jailbreak": JailbreakStrategy,
    "pii_extraction": PiiExtractionStrategy,
    "boundary": BoundaryStrategy,
}


def get_strategy(category: str) -> RedTeamStrategy:
    cls = STRATEGY_REGISTRY.get(category)
    if not cls:
        raise ValueError(f"Unknown red team category: {category}")
    return cls()


def collect_cases(
    categories: list[str], *, enabled_only: bool = True
) -> list[AttackCase]:
    """
    Load cases for all categories, interleaved round-robin.

    Previously cases were blocked by category (all 20 prompt_injection first),
    which made long-running scans look stuck on a single attack type in the UI/logs.
    """
    by_category: dict[str, list[AttackCase]] = {}
    for cat in categories:
        strategy = get_strategy(cat)
        loaded = strategy.load_cases(enabled_only=enabled_only)
        if loaded:
            by_category[cat] = loaded

    if not by_category:
        return []

    ordered_cats = [c for c in categories if c in by_category]
    max_len = max(len(by_category[c]) for c in ordered_cats)
    interleaved: list[AttackCase] = []
    for i in range(max_len):
        for cat in ordered_cats:
            bucket = by_category[cat]
            if i < len(bucket):
                interleaved.append(bucket[i])
    return interleaved
