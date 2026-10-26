import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

MODEL_DIR = PROJECT_ROOT / "models"

console = Console()

def train(repo_path: Path | str):
    """trains Random Forest Regressor on temporal training data and evaluates on held-out test splits
    Saves trained model weights and feature importances
    """
    repo_path = Path(repo_path).resolve()
    repo_name = repo_path.name

    dataset_path = PROJECT_ROOT / "data" / "ml_datasets" / f"{repo_name}_training_dataset.csv"
    if not dataset_path.exists():
        print(f"\n[Notice] No training dataset found for '{repo_name}'. Skipping Random Forest training.")
        return

    with console.status(f"[#b28dff]Loading ML dataset from {dataset_path.name}...", spinner="pong") as status:
        df = pd.read_csv(dataset_path)

        features = [
            "fan_in", "fan_out", "pagerank", "betweenness",
            "historical_commit_count_365d", "historical_corrective_count_365d",
            "historical_cochange_file_count_365d", "historical_cochange_event_count_365d",
            "days_since_last_change"
        ]
        target = "future_cochange_blast_radius_90d"

        train_df = df[df["split"] == "train"]
        test_df = df[df["split"] == "test"]

        X_train, y_train = train_df[features], train_df[target]
        X_test, y_test = test_df[features], test_df[target]

        status.update(f"[#b28dff]Training Random Forest Regressor on {len(X_train)} rows...")
        model = RandomForestRegressor(n_estimators=100, max_depth=12, random_state=42)
        model.fit(X_train, y_train)

        status.update("[#b28dff]Evaluating Model on Held-Out Test Set...")
        predictions = model.predict(X_test)

    rmse = np.sqrt(mean_squared_error(y_test, predictions))
    mae = mean_absolute_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)

    # Heuristic Baseline (Predicting mean blast radius)
    baseline_predictions = np.full_like(y_test, y_train.mean(), dtype=float)
    baseline_rmse = np.sqrt(mean_squared_error(y_test, baseline_predictions))

    # Format tables using Rich
    metrics_table = Table(title="Final Evaluation Metrics", border_style="#b28dff", header_style="bold #ff70a6")
    metrics_table.add_column("Metric", style="#c77dff")
    metrics_table.add_column("Value", style="bold white", justify="right")
    
    metrics_table.add_row("Random Forest RMSE", f"{rmse:.4f}")
    metrics_table.add_row("Baseline RMSE", f"{baseline_rmse:.4f}")
    metrics_table.add_row("Improvement over baseline", f"{baseline_rmse - rmse:.4f} files")
    metrics_table.add_row("Mean Absolute Error", f"{mae:.4f}")
    metrics_table.add_row("R-squared", f"{r2:.4f}")
    
    console.print(metrics_table)

    # Export repository-specific artifacts
    MODEL_DIR.mkdir(exist_ok=True)
    model_output = MODEL_DIR / f"{repo_name}_rf_regressor.joblib"
    joblib.dump(model, model_output)

    importance = pd.DataFrame({
        'Feature': features,
        'Importance': model.feature_importances_
    }).sort_values(by='Importance', ascending=False)
    
    importance_output = MODEL_DIR / f"{repo_name}_feature_importance.csv"
    importance.to_csv(importance_output, index=False)

    feat_table = Table(title="Top Risk Predictors", border_style="#b28dff", header_style="bold #ff70a6")
    feat_table.add_column("Feature", style="#c77dff")
    feat_table.add_column("Importance", justify="right", style="bold white")
    
    for _, row in importance.head(3).iterrows():
        feat_table.add_row(row['Feature'], f"{row['Importance']:.4f}")
        
    console.print(feat_table)
    console.print(f"\n[bold #ff70a6]✔[/bold #ff70a6] Saved trained model to: {model_output}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train ML risk model for a C++ repository.")
    parser.add_argument("repo_path", type=Path, help="Path to target C++ repository")
    args = parser.parse_args()

    train(args.repo_path)