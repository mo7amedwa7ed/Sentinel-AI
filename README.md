# SentinelAI – ML Network Intrusion Detection Dashboard

[![Live Demo](https://img.shields.io/badge/Live-Demo-brightgreen?style=for-the-badge&logo=streamlit)](https://sentinel--ai.streamlit.app/)

SentinelAI is a Streamlit SOC-style dashboard around a trained scikit-learn
Decision Tree. It classifies **uploaded network-flow CSV files** as `BENIGN`
or `ATTACK`.

> **Scope:** this is a batch analyzer for uploaded flow files. It does **not**
> capture packets or monitor a live network, and the model is binary: it does
> **not** identify attack categories.

## What this package contains

Only the new application code. It deliberately does **not** include
`app/predictor.py`, `app/test_predictor.py`, the `Models/` directory, the
notebooks or the datasets. Those are yours and are never modified.

```text
Sentinel AI/                      <- your existing project root
├── Models/                       (yours, untouched; capital M)
│   ├── sentinelai_final_model.pkl
│   ├── median_imputer.pkl
│   └── feature_columns.pkl
├── .streamlit/config.toml        NEW  base dark theme
├── requirements.txt              NEW  (merge if you already have one)
├── README.md                     NEW
├── tests/smoke_test_step1.py     NEW  backend smoke test
└── app/
    ├── __init__.py               NEW  (keep yours if it already exists)
    ├── main.py                   NEW  entry point + navigation
    ├── config.py                 NEW  constants, colours, model facts, metrics
    ├── predictor.py              (yours, untouched)
    ├── test_predictor.py         (yours, untouched)
    ├── components/               NEW  styles.py, cards.py, charts.py
    ├── views/                    NEW  overview, traffic_analysis, threat_detection,
    │                                  analytics, model_info
    └── utils/                    NEW  artifacts, validation, analysis, state
```

`views/` is used instead of `pages/` because Streamlit auto-creates a second
navigation menu from a folder called `pages/`.

## Installation (Windows, Python 3.11)

1. Extract the ZIP **into your project root** (the folder that contains
   `Models/` and `app/`). If asked about overwriting, keep your existing
   `app/predictor.py`, `app/test_predictor.py`, and any existing
   `app/__init__.py` or `requirements.txt` (the ZIP doesn't contain the first two).
2. Create an environment and install dependencies:

```powershell
cd "C:\path\to\Sentinel AI"
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. **Pin scikit-learn** in `requirements.txt` to the exact version you used to
   train (for example `scikit-learn==1.5.2`) and run `pip install -r requirements.txt`
   again. Pickled models can fail or behave differently under another version.

## Run

Always start from the project root:

```powershell
streamlit run app/main.py
```

Open the URL Streamlit prints (default http://localhost:8501).

## Test the backend (no browser needed)

```powershell
python tests\smoke_test_step1.py
```

Expected: `11/11 passed`. The test uses your real artifacts and `predictor.py`
with synthetic rows (training medians), so it checks plumbing only. The
predicted labels it produces mean nothing.

## How it works

1. **Traffic Analysis**: upload a CSV. It is parsed as data only, size-checked
   (200 MB), and validated: all 65 features from `Models/feature_columns.pkl`
   must exist (missing ones are listed), extra columns are ignored,
   `Target`/`Source_Dataset` are never used as input, and non-numeric feature
   values block the analysis with row examples.
2. **Missing / infinite values**: counts per column are reported. `+inf`/`-inf`
   become `NaN`, then `predict_network_traffic` applies the saved median
   imputer. No rows are dropped and no new imputer is fitted.
3. **Threat Detection**: per-flow table with color-coded labels, filters, paging,
   and a CSV report (original columns + `SentinelAI_Prediction`). In downloads,
   text cells starting with `= + - @` get a leading `'` so Excel cannot execute them.
4. **Analytics / Overview**: charts and summaries computed only from the uploaded
   file's predictions.
5. **Model Information**: documented configuration and held-out test-set metrics
   (test set of 853,524 rows), clearly separated from session statistics.

Results persist in Streamlit session state while you switch pages.
Use **Reset session** in the sidebar to clear them.

## Assumptions about `app/predictor.py` (it was not inspected)

1. `from app.predictor import predict_network_traffic` works with the project root
   on `sys.path` (`main.py` adds it).
2. It accepts a DataFrame of the 65 features in training order and returns a list
   of `"BENIGN"`/`"ATTACK"`, one per row, in order.
3. It applies the saved median imputer to `NaN` but does not handle `inf`.
4. It finds `Models/` itself. If it relies on the working directory, launch from the
   project root.

Each assumption is checked at run time; a violation shows a specific error
message instead of crashing. Any fix belongs in `app/utils/analysis.py`.

## Not included on purpose

- **Confusion matrix:** exact test-set counts were not provided. To show it, fill
  `CONFUSION_MATRIX = {"TN": ..., "FP": ..., "FN": ..., "TP": ...}` in
  `app/config.py` with the real values from `04_Model_Evaluation.ipynb`.
- **Negative-value cleanup:** the original pipeline's rule for invalid negative
  measurements is unknown, so negatives are passed through unchanged.
  If you document the rule, it can be added as a separate step in `utils/analysis.py`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `ModuleNotFoundError: app` | Not started from the project root, or `app/__init__.py` missing |
| "Models (capital M) was not found" | Folder renamed or in the wrong place |
| Engine badge shows ERROR | Message under it says which assumption or artifact failed |
| Unpickling / version errors | scikit-learn version differs from the training environment |
| Upload rejected | The message lists missing columns or non-numeric cells |

## Security notes

- Uploaded CSVs are only parsed by `pandas.read_csv`; never evaluated.
- Uploaded text shown in HTML is escaped; file system paths are not shown in the UI.
- `.pkl` files can run code when loaded. Only use artifacts you created.
