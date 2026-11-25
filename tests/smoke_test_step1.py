"""Backend smoke test: validation + analysis pipeline, no Streamlit needed.

Run from the project root:   python tests/smoke_test_step1.py

It uses YOUR real Models/ artifacts and your real app/predictor.py.
Rows are synthetic (training medians repeated) so they test the plumbing
only; the predicted labels carry no meaning and are not performance results.
"""
from __future__ import annotations

import io
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
import pandas as pd

from app import config
from app.utils import analysis as A
from app.utils import validation as V
from app.utils.artifacts import load_feature_columns

FEATURES = list(load_feature_columns())


def make_frame(n: int = 20) -> pd.DataFrame:
    imputer = joblib.load(config.IMPUTER_PATH)
    stats = np.asarray(getattr(imputer, "statistics_", []), dtype=float)
    base = stats if stats.shape[0] == len(FEATURES) and np.isfinite(stats).all() else np.zeros(len(FEATURES))
    return pd.DataFrame(np.tile(base, (n, 1)), columns=FEATURES)


def to_upload(df: pd.DataFrame) -> io.BytesIO:
    return io.BytesIO(df.to_csv(index=False).encode("utf-8"))


# ------------------------------- tests ------------------------------------- #
def t_feature_columns():
    assert len(FEATURES) == 65 and len(set(FEATURES)) == 65


def t_valid_csv_roundtrip():
    df, enc = V.read_uploaded_csv(to_upload(make_frame()))
    res = V.validate_traffic_dataframe(df)
    assert res.is_valid, res.errors
    assert res.n_rows == 20 and not res.quality.has_issues


def t_missing_columns():
    frame = make_frame().drop(columns=FEATURES[:2])
    res = V.validate_traffic_dataframe(frame)
    assert not res.is_valid and res.missing_columns == FEATURES[:2]


def t_extra_and_reserved():
    frame = make_frame()
    frame["Target"], frame["Source_Dataset"], frame["Flow ID"] = 0, "x", "f1"
    res = V.validate_traffic_dataframe(frame)
    assert res.is_valid
    assert set(res.ignored_reserved_columns) == {"Target", "Source_Dataset"}
    assert res.extra_columns == ["Flow ID"]


def t_whitespace_headers():
    frame = make_frame()
    frame = frame.rename(columns={FEATURES[0]: " " + FEATURES[0]})
    res = V.validate_traffic_dataframe(frame)
    assert res.is_valid and res.trimmed_columns == {" " + FEATURES[0]: FEATURES[0]}


def t_non_numeric_blocked():
    frame = make_frame()
    frame[FEATURES[3]] = frame[FEATURES[3]].astype(object)
    frame.loc[4, FEATURES[3]] = "abc"
    res = V.validate_traffic_dataframe(frame)
    assert not res.is_valid and FEATURES[3] in res.non_numeric
    assert res.non_numeric[FEATURES[3]].example_rows == (5,)


def t_quality_counts():
    frame = make_frame()
    frame.loc[0, FEATURES[0]] = np.inf
    frame.loc[1, FEATURES[1]] = -np.inf
    frame.loc[2, FEATURES[2]] = np.nan
    res = V.validate_traffic_dataframe(frame)
    q = res.quality
    assert res.is_valid and len(res.warnings) == 2
    assert q.pos_inf_counts == {FEATURES[0]: 1} and q.neg_inf_counts == {FEATURES[1]: 1}
    assert q.nan_counts == {FEATURES[2]: 1} and q.rows_needing_imputation == 3


def t_empty_and_header_only():
    for payload in (b"", (",".join(FEATURES) + "\n").encode()):
        try:
            V.read_uploaded_csv(io.BytesIO(payload))
        except V.CSVReadError:
            continue
        raise AssertionError("expected CSVReadError")


def t_end_to_end():
    frame = make_frame()
    frame["Target"] = 0
    frame.loc[0, FEATURES[0]] = np.inf
    frame.loc[1, FEATURES[1]] = np.nan
    original = frame.copy()

    result = A.run_analysis(frame, "synthetic.csv")
    assert len(result.report_df) == 20
    assert result.total == 20 and result.benign_count + result.attack_count == 20
    assert result.infinite_cells_converted == 1
    assert "Target" not in result.feature_columns
    assert result.feature_columns == FEATURES
    assert result.report_df.columns[-1] == result.prediction_column
    pd.testing.assert_frame_equal(result.original_df(), original)  # nothing altered
    pd.testing.assert_frame_equal(frame, original)                 # input untouched
    print(f"      (plumbing only) attack={result.attack_count}, benign={result.benign_count}")


def t_export_and_formula_safety():
    frame = make_frame()
    frame["Notes"] = ["=SUM(1+1)", "-5"] + ["ok"] * 18
    result = A.run_analysis(frame, "synthetic.csv")
    export = A.build_report_csv(result)
    assert export.rows == 20 and export.neutralized_cells == 1
    back = pd.read_csv(io.BytesIO(export.data), encoding="utf-8-sig")
    assert back.loc[0, "Notes"] == "'=SUM(1+1)" and back.loc[1, "Notes"] == "-5"
    assert len(back.columns) == len(frame.columns) + 1
    only_attack = A.build_report_csv(result, "ATTACK")
    assert only_attack.rows == result.attack_count


def t_engine_check():
    ok, message = A.check_engine()
    assert ok, message


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("t_")]

if __name__ == "__main__":
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL  {test.__name__}")
            traceback.print_exc()
    print(f"\n{len(TESTS) - failed}/{len(TESTS)} passed")
    sys.exit(1 if failed else 0)
