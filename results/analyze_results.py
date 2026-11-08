"""Summarise the frozen evaluation and analyse the model's errors.

Usage:  RISK_HOME=<storage used for the runs> python results/analyze_results.py leveldb Catch2 abseil-cpp rocksdb
Writes: results/SUMMARY.md and results/<repo>/error_analysis.md
"""
import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import paths                                   # noqa: E402
from graph.impact_report import classify                 # noqa: E402
from ml_pipeline.train_model import FEATURES, TARGET     # noqa: E402

RESULTS = ROOT / "results"
SHOW = ["Random Forest", "Baseline: weighted heuristic", "Baseline: past co-change count",
        "Baseline: previous label", "Baseline: train mean", "Baseline: train median"]
COLS = [("rmse", "RMSE"), ("mae", "MAE"), ("r2", "R²"), ("spearman", "Spearman"), ("ndcg10", "NDCG@10%")]


def kv(path):
    return dict(l.split(": ", 1) for l in path.read_text().splitlines() if ": " in l)


def table(results, bold_best=True):
    best = {k: (min if k in ("rmse", "mae") else max)(r[k] for r in results.values()) for k, _ in COLS}
    rows = ["| Predictor | " + " | ".join(h for _, h in COLS) + " |", "|---" * (len(COLS) + 1) + "|"]
    for name in SHOW:
        if name in results:
            r = results[name]
            cells = [f"**{r[k]:.3f}**" if bold_best and np.isclose(r[k], best[k]) else f"{r[k]:.3f}" for k, _ in COLS]
            rows.append(f"| {name.removeprefix('Baseline: ')} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def error_analysis(repo):
    df = pd.read_csv(paths.datasets_dir() / f"{repo}_training_dataset.csv")
    model = joblib.load(paths.models_dir() / f"{repo}_rf_regressor.joblib")
    te = df[df.split == "test"].copy()
    te["pred"] = model.predict(te[FEATURES])
    te["err"] = te["pred"] - te[TARGET]
    te["kind"] = te["file_path"].map(classify)
    te["bucket"] = pd.cut(te[TARGET], [-0.5, 0.5, 5, 20, np.inf], labels=["0", "1-5", "6-20", ">20"])

    def grp(col):
        g = te.groupby(col, observed=True).agg(rows=(TARGET, "size"), mean_actual=(TARGET, "mean"),
                                                mean_predicted=("pred", "mean"),
                                                mae=("err", lambda e: e.abs().mean()), bias=("err", "mean"))
        return g.round(2).to_markdown()

    worst = te.reindex(te["err"].abs().sort_values(ascending=False).index).head(10)
    worst = worst[["cutoff_date", "file_path", TARGET, "pred", "historical_cochange_file_count_365d", "fan_in"]]
    worst.columns = ["snapshot", "file", "actual", "predicted", "past co-change files", "fan-in"]
    imp = pd.read_csv(paths.models_dir() / f"{repo}_feature_importance.csv")

    under = te[te[TARGET] > 20]["err"].mean() if (te[TARGET] > 20).any() else float("nan")
    zero_over = te[te[TARGET] == 0]["pred"].mean()
    text = f"""# Error analysis: {repo} (held-out test period)

Test rows: {len(te)} · rows with any co-change: {(te[TARGET] > 0).mean():.1%}

## By file kind
{grp("kind")}

## By size of the actual blast radius
{grp("bucket")}

*bias = mean(predicted − actual): negative means the model under-predicts.*

Summary: for files whose real blast radius was above 20, the model's average error was {under:+.1f} files;
for files with no co-change at all, it predicted {zero_over:.2f} on average.

## Ten largest errors
{worst.round(2).to_markdown(index=False)}

## Feature importance
{imp.round(4).to_markdown(index=False)}
"""
    (RESULTS / repo / "error_analysis.md").write_text(text)
    return under, zero_over


def main(repos):
    env = (RESULTS / "environment.txt").read_text()
    out = ["# Evaluation results\n",
           "All runs use the frozen analyzer code (git tag `v1.0-eval`); model and baselines were fixed before "
           "any of these results were produced. Reproduce with `RISK_HOME=... risk build <repo>` at the commits listed.\n",
           "```", env.strip(), "```\n", "## Repositories\n",
           "| Repository | Commit | Commit date | Total commits | Snapshots | Test period | Test rows with activity | Build time |",
           "|---|---|---|---|---|---|---|---|"]
    sections = []
    for repo in repos:
        src = kv(RESULTS / repo / "source.txt")
        m = json.loads((RESULTS / repo / f"{repo}_model_metrics.json").read_text())
        df = pd.read_csv(paths.datasets_dir() / f"{repo}_training_dataset.csv", usecols=["cutoff_date"])
        out.append(f"| {repo} | `{src['commit'][:10]}` | {src['commit_date']} | {src['total_commits']} | "
                   f"{df.cutoff_date.nunique()} | {m['test_from']} → {m['test_to']} | "
                   f"{m['test_active_rows']} of {m['test_rows']} ({m['test_active_rows'] / m['test_rows']:.1%}) | "
                   f"{int(src['build_seconds']) // 60} min {int(src['build_seconds']) % 60} s |")
        s = [f"## {repo}\n", f"### Held-out test period ({m['test_from']} → {m['test_to']})"]
        if m["low_activity_test"]:
            s.append("> ⚠ Low-activity test period: held-out metrics are unreliable for this repository.\n")
        s.append(table(m["held_out"]))
        if m.get("rolling"):
            s += [f"\n### Rolling-origin evaluation ({m['rolling']['folds']} test snapshots)", table(m["rolling"]["results"])]
        under, zero_over = error_analysis(repo)
        s.append(f"\nError analysis: [`{repo}/error_analysis.md`]({repo}/error_analysis.md)\n")
        sections.append("\n".join(s))

    rf_vs = ["\n## Does the Random Forest beat the strongest baseline?\n",
             "| Repository | Evaluation | RF RMSE | Best baseline (RMSE) | RF Spearman | Best baseline Spearman | RF beats best baseline on |",
             "|---|---|---|---|---|---|---|"]
    for repo in repos:
        m = json.loads((RESULTS / repo / f"{repo}_model_metrics.json").read_text())
        evals = [("held-out", m["held_out"])] + ([("rolling", m["rolling"]["results"])] if m.get("rolling") else [])
        for label, res in evals:
            rf = res["Random Forest"]
            base = {k: v for k, v in res.items() if k != "Random Forest"}
            b_rmse = min(base, key=lambda k: base[k]["rmse"])
            b_rho = max(base, key=lambda k: base[k]["spearman"] if not np.isnan(base[k]["spearman"]) else -9)
            wins = [h for k, h in COLS if (rf[k] < min(v[k] for v in base.values()) if k in ("rmse", "mae")
                                          else rf[k] > max(v[k] for v in base.values()))]
            out_label = f"{label}{' ⚠' if label == 'held-out' and m['low_activity_test'] else ''}"
            rf_vs.append(f"| {repo} | {out_label} | {rf['rmse']:.2f} | {b_rmse.removeprefix('Baseline: ')} ({base[b_rmse]['rmse']:.2f}) | "
                         f"{rf['spearman']:.3f} | {base[b_rho]['spearman']:.3f} | {', '.join(wins) or 'none'} |")
    (RESULTS / "SUMMARY.md").write_text("\n".join(out + rf_vs + [""] + sections) + "\n")
    print((RESULTS / "SUMMARY.md").read_text())


if __name__ == "__main__":
    main(sys.argv[1:])
