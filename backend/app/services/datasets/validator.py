"""Dataset schema validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = {"input"}
OPTIONAL_COLUMNS = {
    "expected_output",
    "context",
    "reference",
    "reference_trajectory",
    # Harvested from production traces rather than authored by hand.
    "retrieval_context",
    "conversation",
    "category",
}
ALLOWED_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS

# JSON-valued columns. A CSV round-trip turns these into strings, so they are
# parsed back rather than left as text a metric cannot use.
JSON_COLUMNS = {"reference_trajectory", "retrieval_context", "conversation"}

TEXT_COLUMNS = {"expected_output", "context", "reference", "category"}

CASE_CATEGORIES = [
    "happy_path",
    "edge_case",
    "failure_case",
    "adversarial",
    "long_context",
    "multi_turn",
    "tool_failure",
    "retrieval_failure",
    "ambiguous_request",
    "uncategorized",
]


@dataclass
class ValidatedDataset:
    rows: list[dict[str, Any]]
    row_count: int
    format: str
    warnings: list[str] = field(default_factory=list)


class DatasetValidationError(ValueError):
    pass


def _parse_json_cell(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (list, dict)):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Keep the raw string: better a visible bad value than a silent drop.
        return text


def validate_dataframe(df: pd.DataFrame, fmt: str) -> ValidatedDataset:
    if df.empty:
        raise DatasetValidationError("Dataset must contain at least one row")

    columns = {c.strip().lower() for c in df.columns}
    normalized = {c.strip().lower(): c for c in df.columns}

    if "input" not in columns:
        raise DatasetValidationError(
            f"Missing required column 'input'. Found columns: {list(df.columns)}"
        )

    unknown = columns - ALLOWED_COLUMNS
    if unknown:
        raise DatasetValidationError(
            f"Unsupported columns: {sorted(unknown)}. Allowed: {sorted(ALLOWED_COLUMNS)}"
        )

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        value = row[normalized["input"]]
        if pd.isna(value) or str(value).strip() == "":
            raise DatasetValidationError("All rows must have a non-empty 'input' value")

        record: dict[str, Any] = {"input": str(value).strip()}

        for column in TEXT_COLUMNS & columns:
            cell = row[normalized[column]]
            record[column] = "" if pd.isna(cell) else str(cell).strip()

        for column in JSON_COLUMNS & columns:
            record[column] = _parse_json_cell(row[normalized[column]])

        rows.append(record)

    return ValidatedDataset(
        rows=rows,
        row_count=len(rows),
        format=fmt,
        warnings=_profile_warnings(rows, columns),
    )


def _profile_warnings(rows: list[dict[str, Any]], columns: set[str]) -> list[str]:
    """Surface what this dataset cannot be used to measure.

    A missing column is not an error -- it just means some metrics will report
    themselves unavailable rather than scoring against nothing.
    """
    warnings: list[str] = []
    if "expected_output" not in columns:
        warnings.append(
            "No 'expected_output' column: reference-based metrics "
            "(correctness, contextual recall) will be unavailable."
        )
    if "retrieval_context" not in columns:
        warnings.append(
            "No 'retrieval_context' column: it will be harvested from the agent's "
            "own tool calls at run time, so RAG metrics score what the agent "
            "actually retrieved rather than a fixed reference."
        )
    if "reference_trajectory" not in columns:
        warnings.append(
            "No 'reference_trajectory' column: reference-based trajectory metrics "
            "will be unavailable. Build one from production sessions."
        )
    if "category" not in columns and rows:
        warnings.append(
            "No 'category' column: the distribution of happy paths versus edge "
            "cases cannot be shown, so a high score may only reflect easy cases."
        )
    return warnings


def category_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for row in rows:
        key = (row.get("category") or "uncategorized").strip() or "uncategorized"
        distribution[key] = distribution.get(key, 0) + 1
    return distribution
