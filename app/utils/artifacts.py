"""Read-only access to the saved ML artifacts needed by the UI layer.

Only the feature list is loaded here. The model and imputer are used
exclusively through the existing ``app.predictor`` module, which remains the
single source of truth for prediction.

Security note: joblib/pickle files can execute code when loaded. Only load
artifacts you created yourself (the files in your own ``Models/`` folder).
"""
from __future__ import annotations

from functools import lru_cache

import joblib

from app import config


class ArtifactError(RuntimeError):
    """Raised when a required model artifact is missing or malformed."""


def _check_models_dir() -> None:
    """Verify the directory is named exactly 'Models' (case-sensitive).

    Windows is case-insensitive, so Path('Models').exists() would also be
    True for a folder named 'models'. We compare real directory entries.
    """
    try:
        entries = {p.name for p in config.PROJECT_ROOT.iterdir()}
    except OSError as exc:
        raise ArtifactError("The project directory could not be read.") from exc
    if config.MODELS_DIR_NAME not in entries:
        raise ArtifactError(
            "The required directory 'Models' (capital M) was not found next "
            "to the 'app' folder."
        )


@lru_cache(maxsize=1)
def load_feature_columns() -> tuple[str, ...]:
    """Return the exact, ordered training feature names (cached, immutable)."""
    _check_models_dir()
    path = config.FEATURE_COLUMNS_PATH
    if not path.is_file():
        raise ArtifactError(f"Missing artifact: {config.MODELS_DIR_NAME}/{path.name}")

    try:
        raw = joblib.load(path)
    except Exception as exc:  # corrupt file, version mismatch, ...
        raise ArtifactError(
            f"{path.name} could not be loaded ({type(exc).__name__})."
        ) from exc

    try:
        features = [str(c) for c in list(raw)]
    except TypeError as exc:
        raise ArtifactError(f"{path.name} does not contain a list of names.") from exc

    if len(features) != config.EXPECTED_FEATURE_COUNT:
        raise ArtifactError(
            f"{path.name} lists {len(features)} features; "
            f"{config.EXPECTED_FEATURE_COUNT} were expected."
        )
    if len(set(features)) != len(features):
        raise ArtifactError(f"{path.name} contains duplicate feature names.")
    leaked = [f for f in features if f.strip() in config.RESERVED_COLUMNS]
    if leaked:
        raise ArtifactError(
            f"{path.name} contains reserved non-feature column(s): {leaked}."
        )
    return tuple(features)
