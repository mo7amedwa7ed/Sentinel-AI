"""Orchestrates: validate -> order features -> sanitise -> predict -> report.

All ML work is delegated to the existing ``app.predictor`` module. This file
adds no preprocessing beyond the one approved step: converting +/-infinity to
NaN so the saved median imputer can handle them.

Assumptions about ``app/predictor.py`` (it was not inspected):
  1. ``from app.predictor import predict_network_traffic`` works when the
     project root is on ``sys.path`` (``app/main.py`` arranges this).
  2. The function takes a DataFrame of the 65 features in training order and
     returns one "BENIGN"/"ATTACK" string per row, in row order.
  3. It applies the saved median imputer to NaN values but not to +/-inf.
Every one of these is verified at run time and produces a clear error if wrong.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import numpy as np
import pandas as pd

from app import config
from app.utils.artifacts import ArtifactError, load_feature_columns
from app.utils.validation import (
    ValidationResult,
    build_feature_frame,
    validate_traffic_dataframe,
)


class AnalysisError(Exception):
    """Raised when an analysis cannot be completed. Message is user-safe."""


# --------------------------------------------------------------------------- #
# Result containers
# --------------------------------------------------------------------------- #
@dataclass
class AnalysisResult:
    source_name: str
    analyzed_at: datetime
    duration_seconds: float
    report_df: pd.DataFrame          # original columns + prediction column
    prediction_column: str
    original_columns: list[str]
    feature_columns: list[str]
    validation: ValidationResult
    benign_count: int
    attack_count: int
    infinite_cells_converted: int

    @property
    def total(self) -> int:
        return self.benign_count + self.attack_count

    @property
    def attack_pct(self) -> float:
        return 100.0 * self.attack_count / self.total if self.total else 0.0

    @property
    def benign_pct(self) -> float:
        return 100.0 - self.attack_pct if self.total else 0.0

    @property
    def token(self) -> str:
        """Stable identifier for caching/export matching."""
        return self.analyzed_at.isoformat()

    def original_df(self) -> pd.DataFrame:
        """The uploaded data exactly as parsed (no prediction column)."""
        return self.report_df[self.original_columns]


@dataclass
class ReportExport:
    data: bytes
    rows: int
    neutralized_cells: int


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _safe_message(exc: BaseException, limit: int = 300) -> str:
    """Exception text with the project path removed (no path leakage in the UI)."""
    text = str(exc)
    root = str(config.PROJECT_ROOT)
    for variant in {root, root.replace("\\", "/")}:
        text = text.replace(variant, "<project>")
    return text[:limit]


def _load_predictor() -> Callable[[pd.DataFrame], list[str]]:
    try:
        from app.predictor import predict_network_traffic
    except ModuleNotFoundError as exc:
        if getattr(exc, "name", None) in {"app", "app.predictor"}:
            raise AnalysisError(
                "The prediction module could not be imported. Start the application "
                "from the project root so the 'app' package is importable."
            ) from exc
        raise AnalysisError(
            f"The prediction module needs a missing package: {getattr(exc, 'name', 'unknown')}."
        ) from exc
    except ImportError as exc:
        raise AnalysisError(
            "The function 'predict_network_traffic' could not be imported from "
            "app/predictor.py."
        ) from exc
    except FileNotFoundError as exc:
        raise AnalysisError(
            f"A required model artifact was not found in the '{config.MODELS_DIR_NAME}' directory."
        ) from exc
    except Exception as exc:
        raise AnalysisError(
            f"The prediction module failed to load ({type(exc).__name__})."
        ) from exc
    return predict_network_traffic


def check_engine() -> tuple[bool, str]:
    """Cheap readiness check used by the UI status indicator."""
    try:
        load_feature_columns()
    except ArtifactError as exc:
        return False, str(exc)
    try:
        _load_predictor()
    except AnalysisError as exc:
        return False, str(exc)
    return True, "Detection engine ready"


def _unique_column_name(existing: list[str], base: str) -> str:
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def run_analysis(
    df: pd.DataFrame,
    source_name: str,
    validation: ValidationResult | None = None,
) -> AnalysisResult:
    """Classify every row of ``df`` and build the report DataFrame."""
    started = time.perf_counter()

    validation = validation or validate_traffic_dataframe(df)
    if validation.n_rows != len(df):
        raise AnalysisError("Validation results do not match the supplied data.")
    if not validation.is_valid:
        raise AnalysisError("The file did not pass validation: " + " ".join(validation.errors))

    # 1. Select the 65 features in training order (extra/reserved columns never used).
    model_input, issues = build_feature_frame(df, validation.column_map)
    if issues:  # defensive: validation should already have caught this
        raise AnalysisError("Non-numeric values were found in feature columns.")

    # 2. Approved sanitising step: +/-inf -> NaN. No other values are touched.
    infinite_cells = int(np.isinf(model_input.to_numpy()).sum())
    if infinite_cells:
        model_input = model_input.replace([np.inf, -np.inf], np.nan)

    # 3. Predict through the existing module (it applies the saved imputer).
    predict = _load_predictor()
    try:
        raw_labels = predict(model_input)
    except FileNotFoundError as exc:
        raise AnalysisError(
            f"A required model artifact was not found in the '{config.MODELS_DIR_NAME}' directory."
        ) from exc
    except Exception as exc:
        raise AnalysisError(f"Prediction failed ({type(exc).__name__}): {_safe_message(exc)}") from exc

    # 4. Verify the output contract instead of trusting it.
    labels = [str(x) for x in list(raw_labels)]
    if len(labels) != len(df):
        raise AnalysisError(
            f"The predictor returned {len(labels):,} labels for {len(df):,} rows."
        )
    unexpected = sorted(set(labels) - set(config.VALID_LABELS))
    if unexpected:
        raise AnalysisError(f"The predictor returned unexpected label(s): {unexpected}.")

    # 5. Build the report: all original columns + one appended prediction column.
    original_columns = [str(c) for c in df.columns]
    prediction_column = _unique_column_name(original_columns, config.PREDICTION_COLUMN)
    report_df = df.assign(
        **{prediction_column: pd.Categorical(labels, categories=list(config.VALID_LABELS))}
    )
    if len(report_df) != len(df):
        raise AnalysisError("Row count changed while building the report.")

    attack = int(sum(1 for x in labels if x == config.LABEL_ATTACK))
    return AnalysisResult(
        source_name=source_name,
        analyzed_at=datetime.now(),
        duration_seconds=time.perf_counter() - started,
        report_df=report_df,
        prediction_column=prediction_column,
        original_columns=original_columns,
        feature_columns=list(model_input.columns),
        validation=validation,
        benign_count=len(labels) - attack,
        attack_count=attack,
        infinite_cells_converted=infinite_cells,
    )


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def build_report_csv(
    result: AnalysisResult,
    selection: str = "ALL",
    neutralize_formulas: bool = True,
) -> ReportExport:
    """Serialise the report (original columns + prediction) to CSV bytes.

    ``selection`` is "ALL", "ATTACK" or "BENIGN". When ``neutralize_formulas``
    is on, text cells starting with = + - @ (and not numeric-looking) get a
    leading apostrophe so spreadsheet software never executes them. Numeric
    columns are never altered.
    """
    if selection not in {"ALL", *config.VALID_LABELS}:
        raise ValueError(f"Unknown selection: {selection}")

    out = result.report_df
    if selection != "ALL":
        out = out[out[result.prediction_column] == selection]

    neutralized = 0
    if neutralize_formulas:
        copied = False
        for col in out.columns:
            if pd.api.types.is_numeric_dtype(out[col]) or isinstance(out[col].dtype, pd.CategoricalDtype):
                continue
            as_text = out[col].astype("string")
            starts = as_text.str.startswith(_FORMULA_PREFIXES).fillna(False).to_numpy(dtype=bool)
            numeric_like = pd.to_numeric(as_text, errors="coerce").notna().to_numpy()
            mask = starts & ~numeric_like
            if mask.any():
                if not copied:
                    out = out.copy()
                    copied = True
                out[col] = out[col].astype(object)
                out.loc[mask, col] = "'" + out.loc[mask, col].astype(str)
                neutralized += int(mask.sum())

    data = out.to_csv(index=False).encode("utf-8-sig")  # BOM keeps Excel on Windows happy
    return ReportExport(data=data, rows=len(out), neutralized_cells=neutralized)
