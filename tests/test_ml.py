import numpy as np
import pandas as pd
import pytest

from cpp_risk_analyzer.ml_pipeline.dataset_builder import HORIZON_DAYS
from cpp_risk_analyzer.ml_pipeline.train_model import (TARGET, add_previous_label, all_metrics, purge,
                                     ranking_scores, weighted_heuristic)


def _df(rows):
    return pd.DataFrame(rows, columns=["file_path", "cutoff_date", TARGET])


def test_horizon_is_90_days():
    """The label horizon matches the documented 90-day blast-radius window.
    Req: FR5
    Expected: HORIZON_DAYS == 90
    """
    assert HORIZON_DAYS == 90


def test_purge_removes_overlapping_labels():
    """Training rows whose 90-day label window reaches into the test period are removed.
    Req: NFR2 (valid evaluation; no temporal leakage)
    Expected: with test starting 2024-04-01, rows from 2024-01-01 and 2024-01-02 survive (label windows end on or before 2024-04-01); 2024-02-01 and 2024-03-01 are removed
    """
    d = pd.DataFrame({"cutoff_date": ["2024-01-01", "2024-01-02", "2024-02-01", "2024-03-01"]})
    assert purge(d, "2024-04-01")["cutoff_date"].tolist() == ["2024-01-01", "2024-01-02"]


def test_purge_keeps_everything_with_full_step():
    """With the normal 90-day step, nothing is purged.
    Req: NFR2
    Expected: both rows kept
    """
    d = pd.DataFrame({"cutoff_date": ["2023-10-03", "2024-01-01"]})
    assert len(purge(d, "2024-03-31")) == 2


def test_previous_label_never_uses_unseen_future():
    """The persistence baseline only uses labels fully observed at prediction time.
    Req: NFR2 (no leakage in baselines)
    Expected: a label from 30 days earlier is NOT used (window not finished); one from 90 days earlier is
    """
    df = _df([("a.h", "2024-01-01", 7), ("a.h", "2024-01-31", 3), ("a.h", "2024-04-30", 0)])
    out = add_previous_label(df).sort_values("cutoff_date")
    assert out["previous_label"].tolist() == [0, 0, 3]


def test_weighted_heuristic_fixed_and_scaled():
    """The weighted heuristic is deterministic, ranks higher-signal files higher, and is scaled to the label.
    Req: NFR2, RQ v (manually weighted heuristic baseline)
    Expected: highest-signal file gets the highest prediction; with 3 files (percentile ranks 1/3, 2/3, 1)
              and train mean 3, predictions are [2, 4, 6]
    """
    test = pd.DataFrame({"cutoff_date": ["d"] * 3, "fan_in": [1, 2, 3], "pagerank": [.1, .2, .3],
                         "historical_cochange_file_count_365d": [0, 5, 9],
                         "historical_commit_count_365d": [1, 2, 3]})
    train = pd.DataFrame({TARGET: [2.0, 4.0]})
    p = weighted_heuristic(train, test)
    assert np.argmax(p) == 2
    assert p == pytest.approx([2.0, 4.0, 6.0])
    assert np.allclose(p, weighted_heuristic(train, test))


def test_ranking_perfect_and_constant():
    """Ranking metrics reward correct ordering and give no credit to a constant prediction.
    Req: NFR2 (evaluation metrics)
    Expected: perfect order -> Spearman 1.0, NDCG 1.0; constant prediction -> |Spearman| < 1
    """
    test = pd.DataFrame({"cutoff_date": ["d"] * 10, TARGET: np.arange(10.0)})
    rho, ndcg = ranking_scores(test, np.arange(10.0))
    assert rho == pytest.approx(1.0) and ndcg == pytest.approx(1.0)
    rho_c, _ = ranking_scores(test, np.zeros(10))
    assert abs(rho_c) < 1.0


def test_regression_metrics_known_values():
    """RMSE, MAE and R² match hand-computed values.
    Req: NFR2
    Expected: y=[0,2], p=[1,1] -> RMSE 1, MAE 1, R² 0
    """
    test = pd.DataFrame({"cutoff_date": ["d", "d"], TARGET: [0.0, 2.0]})
    m = all_metrics(test, np.array([1.0, 1.0]))
    assert (m["rmse"], m["mae"], m["r2"]) == (pytest.approx(1.0), pytest.approx(1.0), pytest.approx(0.0))
