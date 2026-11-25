
import sys
import os
import pandas as pd

# Add project root to Python path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app.predictor import predict_network_traffic

# Load a sample from the processed test dataset
test_path = os.path.join(
    BASE_DIR,
    "dataset",
    "processed",
    "test_baseline.parquet"
)

test_df = pd.read_parquet(test_path)

# Select 5 samples
sample = test_df.drop(columns=["Target"]).iloc[:5]

# Predict
predictions = predict_network_traffic(sample)

print("Predictions:")
print(predictions)

print("\nActual:")
print(test_df["Target"].iloc[:5].map({
    0: "BENIGN",
    1: "ATTACK"
}).tolist())
