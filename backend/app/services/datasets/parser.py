"""Parse CSV and JSON evaluation datasets."""

import json
from pathlib import Path

import pandas as pd

from app.services.datasets.validator import (
    DatasetValidationError,
    ValidatedDataset,
    validate_dataframe,
)


def detect_format(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return "csv"
    if lower.endswith(".json"):
        return "json"
    raise DatasetValidationError("Unsupported file format. Use .csv or .json")


def parse_dataset_file(file_path: str | Path) -> ValidatedDataset:
    path = Path(file_path)
    if not path.exists():
        raise DatasetValidationError(f"Dataset file not found: {path}")

    fmt = detect_format(path.name)

    if fmt == "csv":
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            raise DatasetValidationError(f"Failed to parse CSV: {exc}") from exc
        return validate_dataframe(df, fmt)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetValidationError(f"Invalid JSON: {exc}") from exc

    if not isinstance(raw, list):
        raise DatasetValidationError("JSON dataset must be an array of objects")

    df = pd.DataFrame(raw)
    return validate_dataframe(df, fmt)
