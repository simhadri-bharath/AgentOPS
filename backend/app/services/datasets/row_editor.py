"""Read and edit individual dataset rows.

Promotion to `golden` is refused until every row has an `expected_output`.
Without a way to read the rows and fill that field in, that gate is
unsatisfiable -- this module is what makes it reachable.

Edits are written back to the dataset file. CSV sources are rewritten as JSON,
because a reviewed row carries JSON-valued columns (`reference_trajectory`,
`retrieval_context`, `conversation`) that do not survive a CSV round-trip
cleanly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.datasets.parser import parse_dataset_file
from app.services.datasets.validator import CASE_CATEGORIES, DatasetValidationError

logger = get_logger(__name__)

EDITABLE_FIELDS = {"expected_output", "category", "reference_trajectory", "context"}


def read_rows(file_path: str | Path) -> list[dict[str, Any]]:
    return parse_dataset_file(file_path).rows


def row_review_state(row: dict[str, Any]) -> dict[str, Any]:
    """What is still missing before this row can support reference-based metrics."""
    missing: list[str] = []
    if not str(row.get("expected_output") or "").strip():
        missing.append("expected_output")
    if not row.get("reference_trajectory"):
        missing.append("reference_trajectory")
    return {
        "reviewed": not str(row.get("expected_output") or "").strip() == "",
        "missing": missing,
        "blocks_golden": "expected_output" in missing,
    }


def write_rows(file_path: str | Path, rows: list[dict[str, Any]]) -> Path:
    """Persist rows, returning the path actually written.

    A CSV input becomes a sibling .json file so JSON-valued columns survive.
    """
    path = Path(file_path)
    target = path if path.suffix.lower() == ".json" else path.with_suffix(".json")
    target.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if target != path:
        logger.info(
            "Dataset converted to JSON on edit: %s -> %s",
            path.name,
            target.name,
            extra={"component": "dataset_rows"},
        )
    return target


def apply_row_edit(
    rows: list[dict[str, Any]], index: int, changes: dict[str, Any]
) -> dict[str, Any]:
    """Apply an edit to one row in place and return it."""
    if index < 0 or index >= len(rows):
        raise DatasetValidationError(
            f"Row {index} is out of range; dataset has {len(rows)} row(s)"
        )

    unknown = set(changes) - EDITABLE_FIELDS
    if unknown:
        raise DatasetValidationError(
            f"Fields not editable: {sorted(unknown)}. Editable: {sorted(EDITABLE_FIELDS)}"
        )

    category = changes.get("category")
    if category is not None and category not in CASE_CATEGORIES:
        raise DatasetValidationError(
            f"Unknown category '{category}'. Valid: {CASE_CATEGORIES}"
        )

    row = rows[index]
    for key, value in changes.items():
        row[key] = value
    return row


def unreviewed_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for r in rows if not str(r.get("expected_output") or "").strip())
