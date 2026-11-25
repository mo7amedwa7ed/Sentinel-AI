"""Validation of uploaded traffic CSV files.

Responsibilities
----------------
* Read an uploaded file safely (as data only, never evaluated).
* Match the 65 required features (exact names; whitespace-trim fallback).
* Report missing / extra / reserved columns.
* Detect non-numeric cells, NaN and +/-infinity per column.

Nothing here modifies the uploaded data; sanitising happens in analysis.py.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app import config
from app.utils.artifacts import load_feature_columns


class CSVReadError(Exception):
    """Raised when an uploaded file cannot be read as a CSV table."""


# --------------------------------------------------------------------------- #
# Result containers
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class NonNumericIssue:
    count: int
    example_rows: tuple[int, ...]  # 1-based data-row numbers


@dataclass
class DataQualityReport:
    """Missing/infinite value statistics for the 65 feature columns."""

    n_rows: int = 0
    nan_counts: dict[str, int] = field(default_factory=dict)
    pos_inf_counts: dict[str, int] = field(default_factory=dict)
    neg_inf_counts: dict[str, int] = field(default_factory=dict)
    rows_with_nan: int = 0
    rows_with_inf: int = 0
    rows_needing_imputation: int = 0
    all_missing_columns: list[str] = field(default_factory=list)
    mostly_missing_columns: list[str] = field(default_factory=list)

    @property
    def total_nan(self) -> int:
        return sum(self.nan_counts.values())

    @property
    def total_inf(self) -> int:
        return sum(self.pos_inf_counts.values()) + sum(self.neg_inf_counts.values())

    @property
    def has_issues(self) -> bool:
        return bool(self.total_nan or self.total_inf)

    def to_frame(self) -> pd.DataFrame:
        """One row per affected feature, worst first (for display)."""
        names = set(self.nan_counts) | set(self.pos_inf_counts) | set(self.neg_inf_counts)
        rows = []
        for name in names:
            nan = self.nan_counts.get(name, 0)
            pos = self.pos_inf_counts.get(name, 0)
            neg = self.neg_inf_counts.get(name, 0)
            total = nan + pos + neg
            rows.append(
                {
                    "Feature": name,
                    "Missing (NaN)": nan,
                    "+Infinity": pos,
                    "-Infinity": neg,
                    "Affected cells": total,
                    "% of rows": round(100 * total / self.n_rows, 2) if self.n_rows else 0.0,
                }
            )
        columns = ["Feature", "Missing (NaN)", "+Infinity", "-Infinity", "Affected cells", "% of rows"]
        frame = pd.DataFrame(rows, columns=columns)
        return frame.sort_values("Affected cells", ascending=False).reset_index(drop=True)


@dataclass
class ValidationResult:
    n_rows: int
    n_columns: int
    errors: list[str] = field(default_factory=list)      # block analysis
    warnings: list[str] = field(default_factory=list)    # analysis allowed
    notices: list[str] = field(default_factory=list)     # informational
    missing_columns: list[str] = field(default_factory=list)
    extra_columns: list[str] = field(default_factory=list)
    ignored_reserved_columns: list[str] = field(default_factory=list)
    trimmed_columns: dict[str, str] = field(default_factory=dict)  # upload name -> feature
    column_map: dict[str, str] = field(default_factory=dict)       # feature -> upload name
    non_numeric: dict[str, NonNumericIssue] = field(default_factory=dict)
    quality: DataQualityReport = field(default_factory=DataQualityReport)

    @property
    def is_valid(self) -> bool:
        return not self.errors


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #
def _file_size_bytes(file_obj: Any) -> int | None:
    size = getattr(file_obj, "size", None)  # Streamlit UploadedFile
    if isinstance(size, int):
        return size
    try:
        pos = file_obj.tell()
        file_obj.seek(0, io.SEEK_END)
        size = file_obj.tell()
        file_obj.seek(pos)
        return int(size)
    except Exception:
        return None


def read_uploaded_csv(
    file_obj: Any, *, max_mb: int = config.MAX_UPLOAD_MB
) -> tuple[pd.DataFrame, str]:
    """Parse an uploaded file as CSV data. Returns (DataFrame, encoding used).

    The content is only ever parsed by ``pandas.read_csv``; it is never passed
    to eval/exec or any shell.
    """
    size = _file_size_bytes(file_obj)
    if size == 0:
        raise CSVReadError("The uploaded file is empty.")
    if size is not None and size > max_mb * 1024 * 1024:
        raise CSVReadError(
            f"The file is {size / 1024**2:.1f} MB, which exceeds the {max_mb} MB limit."
        )

    df: pd.DataFrame | None = None
    used_encoding = ""
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            file_obj.seek(0)
            df = pd.read_csv(file_obj, encoding=encoding, low_memory=False)
            used_encoding = encoding
            break
        except UnicodeDecodeError:
            continue
        except pd.errors.EmptyDataError:
            raise CSVReadError("The file contains no CSV data (no header row found).") from None
        except pd.errors.ParserError as exc:
            raise CSVReadError(f"The file could not be parsed as CSV: {exc}") from exc
        except (OSError, ValueError) as exc:
            raise CSVReadError(f"The file could not be read: {exc}") from exc

    if df is None:
        raise CSVReadError("The file's text encoding is not supported.")
    if df.shape[0] == 0:
        raise CSVReadError("The file has a header row but no data rows.")

    df.columns = df.columns.map(str)  # guarantee string headers
    return df, used_encoding


# --------------------------------------------------------------------------- #
# Column matching
# --------------------------------------------------------------------------- #
def _fmt_list(names: list[str], limit: int = 15) -> str:
    shown = ", ".join(f"'{n}'" for n in names[:limit])
    extra = len(names) - limit
    return shown + (f" and {extra} more" if extra > 0 else "")


def _resolve_feature_columns(
    columns: list[str], features: list[str]
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Map each required feature to an upload column.

    Exact name wins. Otherwise a column whose name matches after trimming
    leading/trailing whitespace is accepted (and reported). Returns
    (feature->upload name, upload name->feature for trimmed matches,
    features with ambiguous trimmed matches).
    """
    exact = set(columns)
    by_stripped: dict[str, list[str]] = {}
    for col in columns:
        by_stripped.setdefault(col.strip(), []).append(col)

    column_map: dict[str, str] = {}
    trimmed: dict[str, str] = {}
    ambiguous: list[str] = []
    for feature in features:
        if feature in exact:
            column_map[feature] = feature
            continue
        candidates = [c for c in by_stripped.get(feature, []) if c != feature]
        if len(candidates) == 1:
            column_map[feature] = candidates[0]
            trimmed[candidates[0]] = feature
        elif len(candidates) > 1:
            ambiguous.append(feature)
    return column_map, trimmed, ambiguous


# --------------------------------------------------------------------------- #
# Feature extraction and data quality
# --------------------------------------------------------------------------- #
def build_feature_frame(
    df: pd.DataFrame, column_map: dict[str, str]
) -> tuple[pd.DataFrame, dict[str, NonNumericIssue]]:
    """Select the features in exact training order as float64.

    Non-numeric cells become NaN *in this returned frame only* so they can be
    located; callers must treat a non-empty issue dict as a blocking error.
    The uploaded DataFrame itself is never modified.
    """
    features = list(load_feature_columns())
    data: dict[str, pd.Series] = {}
    issues: dict[str, NonNumericIssue] = {}
    for feature in features:
        series = df[column_map[feature]]
        if pd.api.types.is_numeric_dtype(series):
            data[feature] = series.astype("float64")
            continue
        converted = pd.to_numeric(series, errors="coerce")
        bad = (converted.isna() & series.notna()).to_numpy()
        if bad.any():
            rows = tuple(int(i) + 1 for i in np.flatnonzero(bad)[:3])
            issues[feature] = NonNumericIssue(count=int(bad.sum()), example_rows=rows)
        data[feature] = converted.astype("float64")
    return pd.DataFrame(data, index=df.index)[features], issues


def assess_data_quality(frame: pd.DataFrame) -> DataQualityReport:
    """Count NaN, +inf and -inf per column of a numeric feature frame."""
    n_rows = len(frame)
    nan = frame.isna().sum()
    pos = (frame == np.inf).sum()
    neg = (frame == -np.inf).sum()
    combined = nan + pos + neg

    def nonzero(series: pd.Series) -> dict[str, int]:
        return {str(k): int(v) for k, v in series.items() if v > 0}

    rows_nan = frame.isna().any(axis=1)
    rows_inf = np.isinf(frame).any(axis=1)
    threshold = config.HIGH_MISSING_THRESHOLD * n_rows
    return DataQualityReport(
        n_rows=n_rows,
        nan_counts=nonzero(nan),
        pos_inf_counts=nonzero(pos),
        neg_inf_counts=nonzero(neg),
        rows_with_nan=int(rows_nan.sum()),
        rows_with_inf=int(rows_inf.sum()),
        rows_needing_imputation=int((rows_nan | rows_inf).sum()),
        all_missing_columns=[str(c) for c, v in combined.items() if v == n_rows],
        mostly_missing_columns=[
            str(c) for c, v in combined.items() if threshold < v < n_rows
        ],
    )


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def validate_traffic_dataframe(df: pd.DataFrame) -> ValidationResult:
    """Validate an uploaded DataFrame against the model's input contract."""
    features = list(load_feature_columns())
    res = ValidationResult(n_rows=len(df), n_columns=df.shape[1])

    if res.n_rows == 0:
        res.errors.append("The file contains no data rows.")
        return res

    columns = [str(c) for c in df.columns]
    column_map, trimmed, ambiguous = _resolve_feature_columns(columns, features)
    res.column_map = column_map
    res.trimmed_columns = trimmed
    res.missing_columns = [f for f in features if f not in column_map and f not in ambiguous]

    used = set(column_map.values())
    unused = [c for c in columns if c not in used]
    res.ignored_reserved_columns = [c for c in unused if c.strip() in config.RESERVED_COLUMNS]
    res.extra_columns = [c for c in unused if c not in res.ignored_reserved_columns]

    # ---- structural errors ------------------------------------------------ #
    if ambiguous:
        res.errors.append(
            "Ambiguous column names (several headers match after trimming spaces) "
            f"for: {_fmt_list(ambiguous)}."
        )
    if res.missing_columns:
        res.errors.append(
            f"Missing {len(res.missing_columns)} of {config.EXPECTED_FEATURE_COUNT} "
            f"required feature columns: {_fmt_list(res.missing_columns)}."
        )
        if df.shape[1] == 1:
            res.errors.append(
                "Only one column was detected. Check that the file is comma-separated."
            )
    if res.errors:
        return res

    # ---- informational notices ------------------------------------------- #
    if trimmed:
        res.notices.append(
            f"{len(trimmed)} column header(s) matched after trimming leading/trailing "
            "spaces. Original headers are preserved in the report."
        )
    if res.ignored_reserved_columns:
        res.notices.append(
            f"Reserved column(s) {_fmt_list(res.ignored_reserved_columns)} were found. "
            "They are kept in the report but never used as model input."
        )
    if res.extra_columns:
        res.notices.append(
            f"{len(res.extra_columns)} additional column(s) are ignored for prediction "
            "and preserved in the report."
        )

    # ---- numeric check ---------------------------------------------------- #
    frame, issues = build_feature_frame(df, column_map)
    if issues:
        res.non_numeric = issues
        detail = "; ".join(
            f"'{col}': {info.count} cell(s), e.g. row(s) "
            f"{', '.join(map(str, info.example_rows))}"
            for col, info in list(issues.items())[:10]
        )
        res.errors.append(
            f"Non-numeric values found in {len(issues)} feature column(s) ({detail}). "
            "Correct these values and upload the file again."
        )
        return res

    # ---- data quality (warnings only) -------------------------------------- #
    q = assess_data_quality(frame)
    res.quality = q
    if q.total_inf:
        inf_cols = len(set(q.pos_inf_counts) | set(q.neg_inf_counts))
        res.warnings.append(
            f"Found {q.total_inf:,} infinite value(s) in {inf_cols} column(s) across "
            f"{q.rows_with_inf:,} row(s). They will be converted to missing values (NaN) "
            "before prediction."
        )
    if q.total_nan:
        res.warnings.append(
            f"Found {q.total_nan:,} missing value(s) in {len(q.nan_counts)} column(s) across "
            f"{q.rows_with_nan:,} row(s). They will be filled using the median values "
            "saved during training."
        )
    if q.all_missing_columns:
        res.warnings.append(
            f"Column(s) {_fmt_list(q.all_missing_columns)} have no usable values; every "
            "row will receive the training median for them."
        )
    if q.mostly_missing_columns:
        res.warnings.append(
            f"Column(s) {_fmt_list(q.mostly_missing_columns)} are more than "
            f"{int(config.HIGH_MISSING_THRESHOLD * 100)}% missing. Predictions may be "
            "less reliable."
        )
    return res
