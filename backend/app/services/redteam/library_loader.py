"""Load built-in red team JSON attack libraries."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.redteam.strategies.base import AttackCase

_LIBRARIES_DIR = Path(__file__).resolve().parent / "libraries"


@lru_cache(maxsize=8)
def load_library_file(category: str) -> list[dict[str, Any]]:
    path = _LIBRARIES_DIR / f"{category}.json"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "cases" in data:
        return list(data["cases"])
    if isinstance(data, list):
        return data
    return []


def library_to_attack_cases(
    category: str, *, enabled_only: bool = True
) -> list[AttackCase]:
    rows = load_library_file(category)
    cases: list[AttackCase] = []
    for row in rows:
        if enabled_only and row.get("enabled") is False:
            continue
        cases.append(
            AttackCase(
                id=str(row.get("id", "")),
                category=category,
                severity=str(row.get("severity", "medium")),
                prompt=str(row["prompt"]),
                expected_behavior=str(row["expected_behavior"]),
                tags=list(row.get("tags") or []),
                source="library",
                extra=dict(row.get("extra") or {}),
            )
        )
    return cases
