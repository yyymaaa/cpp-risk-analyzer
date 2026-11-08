"""End-to-end tests: run the real CLI on a generated repository with four years of Git history."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import PROJECT_ROOT, make_history_repo

CLI = [sys.executable, "-m", "cpp_risk_analyzer"]


def _run(args, cwd, home, **kw):
    env = {**os.environ, "RISK_HOME": str(home), "COLUMNS": "120",
           "PYTHONPATH": str(PROJECT_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    return subprocess.run(CLI + args, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", stdin=subprocess.DEVNULL, timeout=900, **kw)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Build once for the whole module (the slow step)."""
    root = tmp_path_factory.mktemp("e2e")
    repo = make_history_repo(root)
    home = root / "risk_home"
    result = _run(["build", str(repo)], cwd=repo, home=home)
    return repo, home, result


@pytest.mark.slow
def test_build_produces_all_artifacts(built):
    """`risk build` runs the whole pipeline without MySQL and writes every artifact.
    Req: FR1-FR5, Interface 1, NFR3 (MySQL optional)
    Expected: exit code 0; metrics JSON, dataset CSV, model, feature importances and metrics JSON exist;
              MySQL step reported as skipped, not crashed
    """
    repo, home, r = built
    assert r.returncode == 0, r.stdout + r.stderr
    name = repo.name
    for f in [f"data/extraction_output/{name}_structural_metrics.json",
              f"data/ml_datasets/{name}_training_dataset.csv",
              f"models/{name}_rf_regressor.joblib", f"models/{name}_feature_importance.csv",
              f"models/{name}_model_metrics.json"]:
        assert (home / f).exists(), f
    assert "Traceback" not in r.stdout + r.stderr


@pytest.mark.slow
def test_dataset_is_temporal_and_leak_free(built):
    """The dataset is split by time, and no training label window overlaps the test period.
    Req: FR4, NFR2 (valid evaluation)
    Expected: every train cutoff < every test cutoff; latest train cutoff + 90 days <= first test cutoff
              after purging (recorded as purged_train_rows in metrics)
    """
    import pandas as pd
    repo, home, _ = built
    df = pd.read_csv(home / f"data/ml_datasets/{repo.name}_training_dataset.csv")
    tr, te = df[df.split == "train"], df[df.split == "test"]
    assert tr.cutoff_date.max() < te.cutoff_date.min()
    m = json.loads((home / f"models/{repo.name}_model_metrics.json").read_text())
    kept_max = pd.to_datetime(tr.cutoff_date).sort_values().iloc[-1 - m["purged_train_rows"]] \
        if m["purged_train_rows"] < len(tr) else None
    if kept_max is not None:
        assert kept_max + pd.Timedelta(days=90) <= pd.to_datetime(te.cutoff_date.min())


@pytest.mark.slow
def test_metrics_include_baselines(built):
    """Evaluation output compares the model with all baselines on all metrics.
    Req: NFR2, RQ v
    Expected: metrics JSON has held-out results for Random Forest and 5 baselines incl. the weighted heuristic,
              each with rmse, mae, r2, spearman, ndcg10
    """
    repo, home, _ = built
    m = json.loads((home / f"models/{repo.name}_model_metrics.json").read_text())
    assert "Random Forest" in m["held_out"] and "Baseline: weighted heuristic" in m["held_out"]
    assert len(m["held_out"]) == 6
    for res in m["held_out"].values():
        assert set(res) == {"rmse", "mae", "r2", "spearman", "ndcg10"}


@pytest.mark.slow
def test_impact_report_from_inside_repo(built):
    """`risk impact` works from inside the developer's own codebase and lists files to review and tests to run.
    Req: FR6, Interface 1
    Expected: exit 0; report names core.h, shows REVIEW THESE and the test file core_test.cc
    """
    repo, home, _ = built
    r = _run(["impact", "include/lib/core.h", "--all"], cwd=repo, home=home)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "include/lib/core.h" in r.stdout
    assert "REVIEW" in r.stdout and "core_test.cc" in r.stdout


@pytest.mark.slow
def test_check_fail_on_for_ci(built):
    """`risk check --fail-on` exits non-zero exactly when a change is rated at or above the given level.
    Req: Interface 1 (CI integration)
    Expected: with an uncommitted edit to core.h: --fail-on never -> exit 0; --fail-on moderate -> exit 1
              if the reported grade is MODERATE or worse, else 0
    """
    repo, home, _ = built
    with (repo / "include/lib/core.h").open("a") as f:
        f.write("// uncommitted edit\n")
    try:
        never = _run(["check", "--no-staged", "--fail-on", "never"], cwd=repo, home=home)
        assert never.returncode == 0, never.stdout + never.stderr
        assert "core.h" in never.stdout
        risky = any(g in never.stdout for g in ("MODERATE", "HIGH", "CRITICAL"))
        mod = _run(["check", "--no-staged", "--fail-on", "moderate"], cwd=repo, home=home)
        assert mod.returncode == (1 if risky else 0), mod.stdout
    finally:
        subprocess.run(["git", "-C", str(repo), "checkout", "-q", "."], check=True)


@pytest.mark.slow
def test_no_model_does_not_hang(built, tmp_path):
    """Without a model and without a terminal, commands exit with guidance instead of waiting forever.
    Req: Usability / robustness
    Expected: exit code 1 within the timeout; message tells the user to run `risk build`
    """
    repo, _, _ = built
    r = _run(["impact", "include/lib/core.h"], cwd=repo, home=tmp_path / "empty_home")
    assert r.returncode == 1
    assert "risk build" in r.stdout
