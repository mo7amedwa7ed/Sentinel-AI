"""Central configuration for SentinelAI.

Everything that is a constant lives here: filesystem paths, label names,
the colour system, upload limits and the documented model facts. Nothing in
this module performs I/O.
"""
from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths (resolved from this file, never from the current working directory)
# --------------------------------------------------------------------------- #
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
MODELS_DIR_NAME: str = "Models"  # capital M, strictly
MODELS_DIR: Path = PROJECT_ROOT / MODELS_DIR_NAME

MODEL_PATH: Path = MODELS_DIR / "sentinelai_final_model.pkl"
IMPUTER_PATH: Path = MODELS_DIR / "median_imputer.pkl"
FEATURE_COLUMNS_PATH: Path = MODELS_DIR / "feature_columns.pkl"

# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #
APP_NAME: str = "SentinelAI"
APP_TAGLINE: str = "Machine Learning Network Intrusion Detection"
PAGES: tuple[str, ...] = (
    "Overview",
    "Traffic Analysis",
    "Threat Detection",
    "Analytics",
    "Model Information",
)

# --------------------------------------------------------------------------- #
# Labels
# --------------------------------------------------------------------------- #
LABEL_BENIGN: str = "BENIGN"
LABEL_ATTACK: str = "ATTACK"
VALID_LABELS: tuple[str, ...] = (LABEL_BENIGN, LABEL_ATTACK)
PREDICTION_COLUMN: str = "SentinelAI_Prediction"

# --------------------------------------------------------------------------- #
# Input rules
# --------------------------------------------------------------------------- #
EXPECTED_FEATURE_COUNT: int = 65
# Columns that may exist in processed data but must NEVER be model input.
RESERVED_COLUMNS: tuple[str, ...] = ("Target", "Source_Dataset")
MAX_UPLOAD_MB: int = 200
HIGH_MISSING_THRESHOLD: float = 0.5  # warn when a column is >50% missing
PREVIEW_ROWS: int = 100
HISTORY_LIMIT: int = 25
ANALYTICS_SAMPLE_PER_CLASS: int = 25_000  # row cap per class for distribution plots

# --------------------------------------------------------------------------- #
# Colour system (SOC dark theme)
# --------------------------------------------------------------------------- #
COLORS: dict[str, str] = {
    "bg": "#0B1220",
    "surface": "#111A2E",
    "surface_alt": "#16213A",
    "border": "#22304D",
    "text": "#E6EDF7",
    "text_muted": "#8A9BB8",
    "accent": "#22D3EE",
    "benign": "#22C55E",
    "attack": "#EF4444",
    "warning": "#F59E0B",
}

# --------------------------------------------------------------------------- #
# Documented model facts (taken from the project specification)
# --------------------------------------------------------------------------- #
MODEL_INFO: dict[str, str | int] = {
    "Model name": "Decision Tree Classifier",
    "Model type": "Binary Classification",
    "Number of features": EXPECTED_FEATURE_COUNT,
    "Training framework": "Scikit-learn",
    "Output classes": "BENIGN (0) / ATTACK (1)",
}

MODEL_CONFIG: dict[str, str | int] = {
    "criterion": "gini",
    "max_depth": 25,
    "min_samples_split": 5,
    "min_samples_leaf": 1,
    "class_weight": "balanced",
    "random_state": 42,
}

# Held-out test-set results (percent). These are historical evaluation
# results, NOT live statistics about uploaded traffic.
TEST_SET_SIZE: int = 853_524
EVALUATION_METRICS: dict[str, float] = {
    "Accuracy": 99.8931,
    "Precision": 99.6249,
    "Recall": 99.8580,
    "F1-score": 99.7413,
    "ROC-AUC": 99.8906,
    "PR-AUC": 99.5829,
}

# Exact confusion-matrix counts were not provided, so none are shown.
# Set to {"TN": .., "FP": .., "FN": .., "TP": ..} ONLY with real values taken
# from 04_Model_Evaluation.ipynb; the Model Information page then renders it.
CONFUSION_MATRIX: dict[str, int] | None = None
