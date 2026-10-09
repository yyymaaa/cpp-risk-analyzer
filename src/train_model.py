import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = PROJECT_ROOT / "training_dataset.csv"
MODEL_DIR = PROJECT_ROOT / "models"

def train():
    print("Loading dataset...")
    df = pd.read_csv(DATASET_PATH)

    # The 9 original features
    features = [
        "fan_in", "fan_out", "pagerank", "betweenness",
        "historical_commit_count_365d", "historical_corrective_count_365d",
        "historical_cochange_file_count_365d", "historical_cochange_event_count_365d",
        "days_since_last_change"
    ]
    
    # Our new Path A continuous target
    target = "future_cochange_blast_radius_90d"

    train_df = df[df["split"] == "train"]
    test_df = df[df["split"] == "test"]

    X_train = train_df[features]
    y_train = train_df[target]
    X_test = test_df[features]
    y_test = test_df[target]

    print(f"Training Random Forest Regressor on {len(X_train)} rows...")
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    print("Evaluating Model on Held-Out Test Set...")
    predictions = model.predict(X_test)

    rmse = np.sqrt(mean_squared_error(y_test, predictions))
    mae = mean_absolute_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)

    # Heuristic Baseline (Predicting the mean blast radius)
    baseline_predictions = np.full_like(y_test, y_train.mean(), dtype=float)
    baseline_rmse = np.sqrt(mean_squared_error(y_test, baseline_predictions))

    print("\n--- Final Evaluation Metrics ---")
    print(f"Random Forest RMSE:  {rmse:.4f}")
    print(f"Baseline RMSE:       {baseline_rmse:.4f}")
    print(f"Improvement over baseline: {baseline_rmse - rmse:.4f} fewer files of error")
    print(f"Mean Absolute Error: {mae:.4f}")
    print(f"R-squared:           {r2:.4f}")

    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_DIR / "random_forest_regressor.joblib")
    
    # Save feature importance to satisfy the explainability requirement
    importance = pd.DataFrame({
        'Feature': features,
        'Importance': model.feature_importances_
    }).sort_values(by='Importance', ascending=False)
    
    importance.to_csv(MODEL_DIR / "feature_importance.csv", index=False)
    
    print("\nTop 3 Risk Predictors (Feature Importance):")
    print(importance.head(3).to_string(index=False))

if __name__ == "__main__":
    train()