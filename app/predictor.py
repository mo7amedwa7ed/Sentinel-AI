
import os
import joblib
import pandas as pd


# Project paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "Models")


# Load saved artifacts
model = joblib.load(
    os.path.join(MODELS_DIR, "sentinelai_final_model.pkl")
)

imputer = joblib.load(
    os.path.join(MODELS_DIR, "median_imputer.pkl")
)

feature_columns = joblib.load(
    os.path.join(MODELS_DIR, "feature_columns.pkl")
)


def predict_network_traffic(input_data):

    if not isinstance(input_data, pd.DataFrame):
        input_data = pd.DataFrame(input_data)

    missing_features = set(feature_columns) - set(input_data.columns)

    if missing_features:
        raise ValueError(
            f"Missing features: {sorted(missing_features)}"
        )

    input_data = input_data[feature_columns]

    input_imputed = pd.DataFrame(
        imputer.transform(input_data),
        columns=feature_columns,
        index=input_data.index
    )

    predictions = model.predict(input_imputed)

    labels = {
        0: "BENIGN",
        1: "ATTACK"
    }

    return [labels[prediction] for prediction in predictions]
