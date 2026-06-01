"""Build and filter red team attack case lists for runs."""

from __future__ import annotations

from app.repositories.redteam_repository import RedTeamRepository
from app.services.redteam.strategies.base import AttackCase
from app.services.redteam.strategies.registry import collect_cases


def case_selection_key(case: AttackCase) -> str:
    """Stable id sent by the UI (library external_id or DB UUID)."""
    return case.db_id or case.id


def filter_cases_by_ids(
    cases: list[AttackCase], selected_case_ids: list[str] | None
) -> list[AttackCase]:
    if selected_case_ids is None:
        return cases
    allowed = {s.strip() for s in selected_case_ids if s and s.strip()}
    if not allowed:
        return []
    return [
        c
        for c in cases
        if case_selection_key(c) in allowed or c.id in allowed
    ]


async def build_run_cases(
    repo: RedTeamRepository,
    *,
    categories: list[str],
    include_custom_cases: bool = True,
    selected_case_ids: list[str] | None = None,
) -> list[AttackCase]:
    """Collect library + optional custom cases, then apply prompt selection."""
    all_cases = collect_cases(categories, enabled_only=True)

    if include_custom_cases:
        db_cases, _ = await repo.list_test_cases(enabled_only=True, limit=500, offset=0)
        for row in db_cases:
            if row.category not in categories:
                continue
            all_cases.append(
                AttackCase(
                    id=row.external_id or str(row.id),
                    category=row.category,
                    severity=row.severity,
                    prompt=row.prompt,
                    expected_behavior=row.expected_behavior,
                    tags=list(row.tags or []),
                    source=row.source,
                    db_id=str(row.id),
                )
            )

    filtered = filter_cases_by_ids(all_cases, selected_case_ids)

    if selected_case_ids:
        unknown = set(selected_case_ids) - {
            case_selection_key(c) for c in filtered
        } - {c.id for c in filtered}
        if unknown:
            # Allow stale ids without failing the run; log via caller if needed
            pass

    return filtered


def validate_selected_ids(
    cases: list[AttackCase],
    categories: list[str],
    selected_case_ids: list[str] | None,
) -> None:
    """Raise ValueError when selection is inconsistent."""
    if not cases:
        raise ValueError("No test cases match the selected categories and prompts.")
    if not selected_case_ids:
        return
    by_cat: dict[str, int] = {}
    for c in cases:
        by_cat[c.category] = by_cat.get(c.category, 0) + 1
    for cat in categories:
        if cat not in by_cat:
            raise ValueError(
                f"Category '{cat}' has no selected prompts. "
                "Pick at least one attack per enabled category."
            )
