"""Dataset schema validation."""

from dataclasses import dataclass

import pandas as pd

REQUIRED_COLUMNS = {"input"}
OPTIONAL_COLUMNS = {"expected_output", "context", "reference","reference_trajectory"}
ALLOWED_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS


@dataclass
class ValidatedDataset:
    rows: list[dict[str, str]]
    row_count: int
    format: str


class DatasetValidationError(ValueError):
    pass


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
        raise DatasetValidationError(f"Unsupported columns: {sorted(unknown)}")

    rows: list[dict[str, str]] = []
    for _, row in df.iterrows():
        input_col = normalized["input"]
        inp = row[input_col]
        if pd.isna(inp) or str(inp).strip() == "":
            raise DatasetValidationError("All rows must have a non-empty 'input' value")

        record: dict[str, str] = {"input": str(inp).strip()}
        if "expected_output" in columns:
            exp_col = normalized["expected_output"]
            val = row[exp_col]
            record["expected_output"] = "" if pd.isna(val) else str(val).strip()
        if "context" in columns:
            ctx_col = normalized["context"]
            val = row[ctx_col]
            record["context"] = "" if pd.isna(val) else str(val).strip()
        if "reference" in columns:
            ref_col = normalized["reference"]
            val = row[ref_col]
            record["reference"] = "" if pd.isna(val) else str(val).strip()
        rows.append(record)
        if "reference_trajectory" in columns:
            rt_col = normalized["reference_trajectory"]
            val = row[rt_col]
            if pd.isna(val) or str(val).strip() == "":
                record["reference_trajectory"] = None
            else:
                import json
                raw_val = str(val).strip()
                try:
                    record["reference_trajectory"] = json.loads(raw_val)
                except json.JSONDecodeError:
                    record["reference_trajectory"] = raw_val

    return ValidatedDataset(rows=rows, row_count=len(rows), format=fmt)
