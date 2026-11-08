import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core import paths

import joblib
import numpy as np
import pandas as pd
import json

from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, ndcg_score

from ml_pipeline.dataset_builder import HORIZON_DAYS



FEATURES = [
    "fan_in", "fan_out", "pagerank", "betweenness",
    "historical_commit_count_365d", "historical_corrective_count_365d",
    "historical_cochange_file_count_365d", "historical_cochange_event_count_365d",
    "days_since_last_change"
]
TARGET = "future_cochange_blast_radius_90d"

# Rolling evaluation needs enough history before the first test snapshot
MIN_TRAIN_SNAPSHOTS = 8
# Below these, the test period is too quiet for the metrics to mean much
MIN_ACTIVE_TEST_ROWS = 50
MIN_ACTIVE_TEST_SHARE = 0.05

console = Console()


def make_model():
    """Single definition of the model so the held-out and rolling evaluations train the same thing."""
    return RandomForestRegressor(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1)


def purge(train_df, test_start):
    """Drop training rows whose 90-day label window reaches into the test period.

    Each row's label counts co-changes in (cutoff, cutoff + HORIZON_DAYS]. If that window
    ends after the first test cutoff, the label contains test-period information (leakage).
    This only happens when dataset_builder shrinks the snapshot step below HORIZON_DAYS.
    """
    label_end = pd.to_datetime(train_df["cutoff_date"]) + pd.Timedelta(days=HORIZON_DAYS)
    return train_df[label_end <= pd.to_datetime(test_start)]


def add_previous_label(df):
    """Persistence baseline: each file's most recent label that was fully observed at cutoff time,
    i.e. from a snapshot at least HORIZON_DAYS earlier (otherwise it would leak). 0 if none."""
    df = df.copy()
    df["_date"] = pd.to_datetime(df["cutoff_date"])
    past = df[["file_path", "_date", TARGET]].rename(columns={TARGET: "previous_label"})
    past["_date"] = past["_date"] + pd.Timedelta(days=HORIZON_DAYS)   # when that label became known
    df = df.sort_values("_date")
    past = past.sort_values("_date")
    df = pd.merge_asof(df, past, on="_date", by="file_path", direction="backward")
    df["previous_label"] = df["previous_label"].fillna(0)
    return df.drop(columns="_date")


HEURISTIC_WEIGHTS = {   # fixed a priori (equal weights, no tuning): 2 structural + 2 historical signals
    "fan_in": 0.25,
    "pagerank": 0.25,
    "historical_cochange_file_count_365d": 0.25,
    "historical_commit_count_365d": 0.25,
}


def weighted_heuristic(train_df, test_df):
    """Manually weighted heuristic baseline (RQ v / NFR 2).

    Each signal is converted to its percentile rank within the file's snapshot (so repositories
    and snapshots of different sizes are comparable), combined with HEURISTIC_WEIGHTS, and scaled
    so its average equals the training-label mean (the average weighted rank is 0.5).
    """
    score = sum(w * test_df.groupby("cutoff_date")[col].rank(pct=True)
                for col, w in HEURISTIC_WEIGHTS.items())
    return score.to_numpy() * 2 * train_df[TARGET].mean()


def baseline_predictions(train_df, test_df):
    """Simple non-ML predictors the Random Forest must beat to be worth using."""
    mean = train_df[TARGET].mean()
    hist_mean = max(train_df["historical_cochange_file_count_365d"].mean(), 1e-9)
    return {
        "Baseline: weighted heuristic": weighted_heuristic(train_df, test_df),
        "Baseline: train mean": np.full(len(test_df), mean),
        "Baseline: train median": np.full(len(test_df), train_df[TARGET].median()),
        "Baseline: previous label": test_df["previous_label"].to_numpy(dtype=float),
        "Baseline: past co-change count": test_df["historical_cochange_file_count_365d"].to_numpy() * mean / hist_mean,
    }


def ranking_scores(test_df, predictions):
    """How well predictions rank files *within each snapshot* (what `risk impact` uses).

    Returns mean Spearman correlation and mean NDCG@10% across snapshots that have
    at least two different label values. Ties are broken randomly (fixed seed) so a
    constant prediction scores as chance rather than getting lucky from sort order.
    """
    rng = np.random.default_rng(42)
    rhos, ndcgs = [], []
    y_all = test_df[TARGET].to_numpy()
    for idx in test_df.groupby("cutoff_date").indices.values():
        y = y_all[idx]
        if len(idx) < 5 or y.std() == 0:
            continue
        p = predictions[idx] + rng.uniform(0, 1e-9, len(idx))
        rhos.append(spearmanr(y, p).correlation)
        ndcgs.append(ndcg_score([y], [p], k=max(1, int(0.10 * len(idx)))))
    return (float(np.mean(rhos)) if rhos else float("nan"),
            float(np.mean(ndcgs)) if ndcgs else float("nan"))


def all_metrics(test_df, predictions):
    y = test_df[TARGET].to_numpy()
    spearman, ndcg = ranking_scores(test_df, predictions)
    return {
        "rmse": float(np.sqrt(mean_squared_error(y, predictions))),
        "mae": float(mean_absolute_error(y, predictions)),
        "r2": float(r2_score(y, predictions)),
        "spearman": spearman,
        "ndcg10": ndcg,
    }


def rolling_evaluation(df):
    """Rolling-origin evaluation: for every snapshot T (after the first MIN_TRAIN_SNAPSHOTS),
    train on purged earlier snapshots and predict T. Tests every period of the project's history
    instead of only the final 20%, which may be unusually quiet or busy."""
    dates = sorted(df["cutoff_date"].unique())
    folds = []
    for test_date in dates:
        train_df = purge(df[df["cutoff_date"] < test_date], test_date)
        test_df = df[df["cutoff_date"] == test_date].copy()
        if train_df["cutoff_date"].nunique() < MIN_TRAIN_SNAPSHOTS or test_df.empty:
            continue
        model = make_model().fit(train_df[FEATURES], train_df[TARGET])
        test_df["pred::Random Forest"] = model.predict(test_df[FEATURES])
        for name, p in baseline_predictions(train_df, test_df).items():
            test_df[f"pred::{name}"] = p
        folds.append(test_df)

    if not folds:
        return None, 0
    pooled = pd.concat(folds).reset_index(drop=True)
    results = {c.split("::", 1)[1]: all_metrics(pooled, pooled[c].to_numpy())
               for c in pooled.columns if c.startswith("pred::")}
    return results, len(folds)


def metrics_table(title, results):
    table = Table(title=title, border_style="#b28dff", header_style="bold #ff70a6")
    table.add_column("Predictor", style="#c77dff")
    for col in ["RMSE", "MAE", "R²", "Spearman", "NDCG@10%"]:
        table.add_column(col, style="bold white", justify="right")
    best_rmse = min(r["rmse"] for r in results.values())
    for name, r in results.items():
        mark = " ★" if r["rmse"] == best_rmse else ""
        table.add_row(name + mark, f"{r['rmse']:.3f}", f"{r['mae']:.3f}", f"{r['r2']:.3f}",
                      f"{r['spearman']:.3f}", f"{r['ndcg10']:.3f}")
    return table


def train(repo_path: Path | str, rolling: bool = True):
    """trains Random Forest Regressor on temporal training data and evaluates on held-out test splits
    against simple baselines, optionally with rolling-origin evaluation.
    Saves trained model weights, feature importances and evaluation metrics.
    """
    repo_path = Path(repo_path).resolve()
    repo_name = repo_path.name

    dataset_path = paths.datasets_dir() / f"{repo_name}_training_dataset.csv"
    if not dataset_path.exists():
        print(f"\n[Notice] No training dataset found for '{repo_name}'. Skipping Random Forest training.")
        return

    with console.status(f"[#b28dff]Loading ML dataset from {dataset_path.name}...", spinner="pong") as status:
        df = add_previous_label(pd.read_csv(dataset_path))

        test_df = df[df["split"] == "test"].reset_index(drop=True)
        test_start = test_df["cutoff_date"].min()
        unpurged = df[df["split"] == "train"]
        train_df = purge(unpurged, test_start).reset_index(drop=True)
        n_purged = len(unpurged) - len(train_df)

        X_train, y_train = train_df[FEATURES], train_df[TARGET]
        X_test, y_test = test_df[FEATURES], test_df[TARGET]

        status.update(f"[#b28dff]Training Random Forest Regressor on {len(X_train)} rows...")
        model = make_model()
        model.fit(X_train, y_train)

        status.update("[#b28dff]Evaluating Model on Held-Out Test Set...")
        predictions = model.predict(X_test)

        held_out = {"Random Forest": all_metrics(test_df, predictions)}
        for name, p in baseline_predictions(train_df, test_df).items():
            held_out[name] = all_metrics(test_df, p)

        rolling_results, n_folds = (None, 0)
        if rolling:
            status.update("[#b28dff]Rolling-origin evaluation (retrains once per snapshot)...")
            rolling_results, n_folds = rolling_evaluation(df)

    if n_purged:
        console.print(f"[#ffb8d1]Purged {n_purged} training rows whose 90-day label window overlapped the test period.[/]")

    # Warn when the held-out period is too quiet for its metrics to be trusted
    active_rows = int((y_test > 0).sum())
    active_share = active_rows / max(len(y_test), 1)
    low_activity = active_rows < MIN_ACTIVE_TEST_ROWS or active_share < MIN_ACTIVE_TEST_SHARE
    if low_activity:
        console.print(
            f"[bold #ff0a54]⚠ Low-activity test period:[/] only {active_rows} of {len(y_test)} test rows "
            f"({active_share:.1%}) have any co-change. Held-out metrics are unreliable for this repository; "
            f"rely on the rolling evaluation and treat results as a limitation."
        )

    rf = held_out["Random Forest"]
    baseline_rmse = held_out["Baseline: train mean"]["rmse"]
    best_baseline = min((k for k in held_out if k != "Random Forest"), key=lambda k: held_out[k]["rmse"])

    # Export JSON Metadata (r2/rmse/mae/baseline_rmse/test_from/test_to are read by impact_report.py)
    trust = {
        "r2": rf["r2"], "rmse": rf["rmse"], "mae": rf["mae"],
        "baseline_rmse": float(baseline_rmse),
        "best_baseline": best_baseline,
        "best_baseline_rmse": held_out[best_baseline]["rmse"],
        "spearman": rf["spearman"], "ndcg10": rf["ndcg10"],
        "train_rows": int(len(train_df)), "test_rows": int(len(test_df)),
        "purged_train_rows": int(n_purged),
        "test_active_rows": active_rows, "low_activity_test": bool(low_activity),
        "test_from": str(test_df["cutoff_date"].min())[:10],
        "test_to": str(test_df["cutoff_date"].max())[:10],
        "held_out": held_out,
        "rolling": {"folds": n_folds, "results": rolling_results} if rolling_results else None,
    }

    MODEL_DIR = paths.models_dir()
    (MODEL_DIR / f"{repo_name}_model_metrics.json").write_text(json.dumps(trust, indent=2))

    console.print(metrics_table(f"Held-Out Evaluation ({trust['test_from']} → {trust['test_to']})", held_out))
    if rolling_results:
        console.print(metrics_table(f"Rolling Evaluation ({n_folds} snapshots)", rolling_results))
    elif rolling:
        console.print(f"[#ffb8d1]Rolling evaluation skipped: needs at least {MIN_TRAIN_SNAPSHOTS} earlier "
                      f"snapshots before a test snapshot, but this dataset has only "
                      f"{df['cutoff_date'].nunique()} snapshots in total. Is the repository a shallow clone "
                      f"(`git rev-parse --is-shallow-repository`)?[/]")

    verdict = "beats" if rf["rmse"] < held_out[best_baseline]["rmse"] else "does NOT beat"
    console.print(f"[#c77dff]Random Forest {verdict} the strongest baseline ({best_baseline}) on held-out RMSE.[/]")

    # Export repository-specific artifacts
    model_output = MODEL_DIR / f"{repo_name}_rf_regressor.joblib"
    joblib.dump(model, model_output)

    importance = pd.DataFrame({
        'Feature': FEATURES,
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
    parser.add_argument("--no-rolling", action="store_true",
                        help="Skip rolling-origin evaluation (faster; held-out split only)")
    args = parser.parse_args()

    train(args.repo_path, rolling=not args.no_rolling)
