from types import SimpleNamespace

import pytest
import typer

from core import paths
from graph.cochange import CoChangeIndex
from graph.impact_report import classify, compute_report, trust_line
from tests.test_graph import _graph


def _fallback_analyzer(repo, commits=()):
    """Analyzer stand-in without a model (structural fallback mode)."""
    from graph.analyzer import StructuralAnalyzer
    g = _graph(repo)
    return SimpleNamespace(graph=g, cochange=CoChangeIndex(list(commits)), has_model=False,
                           metrics=StructuralAnalyzer(g).calculate_metrics(), trust=None)


def test_classify_file_kinds():
    """Files are classified as product code, tests or tooling.
    Req: FR6 (prescriptive report)
    Expected: tests/x_test.cc -> test, tools/cli.cc -> tool, src/a.cc -> prod
    """
    assert classify("tests/core_test.cc") == "test"
    assert classify("tools/cli.cc") == "tool"
    assert classify("src/api.cc") == "prod"


def test_impact_finds_all_dependents(tiny_repo):
    """Impact analysis finds every file that directly or transitively includes the target.
    Req: FR6
    Expected: changing core.h reaches 6 files; engine.cc is 2 hops away via util.h
    """
    r = compute_report(_fallback_analyzer(tiny_repo), "include/lib/core.h")
    assert r.reachable == 6
    engine = next(h for h in r.hits if h.file == "src/engine.cc")
    assert engine.dist == 2


def test_impact_tiers(tiny_repo):
    """Product code goes to REVIEW/WATCH, tests to RUN, tooling never to REVIEW.
    Req: FR6 (maps downstream files to testing actions)
    Expected: tests/core_test.cc tier RUN; tools/cli.cc not REVIEW; at least one product file in REVIEW
    """
    r = compute_report(_fallback_analyzer(tiny_repo), "include/lib/core.h")
    tier = {h.file: h.tier for h in r.hits}
    assert tier["tests/core_test.cc"] == "RUN"
    assert tier["tools/cli.cc"] != "REVIEW"
    assert any(h.tier == "REVIEW" and h.kind == "prod" for h in r.hits)


def test_cochange_history_raises_score(tiny_repo):
    """A dependent that historically changes with the target scores higher than an identical one that does not.
    Req: FR2, FR6
    Expected: util.h (co-changed in 5/5 commits) scores above api.h (never co-changed), both 1 hop away
    """
    commits = [["include/lib/core.h", "include/lib/util.h"]] * 5
    r = compute_report(_fallback_analyzer(tiny_repo, commits), "include/lib/core.h")
    s = {h.file: h.score for h in r.hits}
    assert s["include/lib/util.h"] > s["include/lib/api.h"]


def test_unrelated_file_has_no_impact(tiny_repo):
    """A file nothing depends on has an empty impact set and the lowest grade.
    Req: FR6
    Expected: engine.cc reaches 0 files; grade LOW
    """
    r = compute_report(_fallback_analyzer(tiny_repo), "src/engine.cc")
    assert (r.reachable, r.grade) == (0, "LOW")


def test_trust_line_reports_accuracy_honestly():
    """The report states measured accuracy, the best baseline and low-activity warnings.
    Req: FR6, honest uncertainty (Sprint III)
    Expected: text contains R², both baseline errors and the warning
    """
    t = {"r2": 0.34, "rmse": 12.4, "baseline_rmse": 15.4, "best_baseline_rmse": 12.7,
         "low_activity_test": True, "test_from": "2023-10-16", "test_to": "2026-07-02"}
    s = trust_line(t, has_model=True)
    assert "R² 0.34" in s and "±12.7" in s and "±15.4" in s and "little activity" in s


def test_paths_risk_home(risk_home):
    """RISK_HOME overrides where models and data are stored.
    Req: Deployment (pip install works outside the project folder)
    Expected: models_dir() and datasets_dir() are inside RISK_HOME
    """
    assert paths.models_dir() == risk_home / "models"
    assert paths.datasets_dir() == risk_home / "data" / "ml_datasets"


def test_paths_user_data_dir_when_installed(monkeypatch, tmp_path):
    """When installed (no source checkout) data goes to the per-user data folder.
    Req: Deployment
    Expected: storage_root() == $XDG_DATA_HOME/cpp-risk-analyzer
    """
    monkeypatch.delenv("RISK_HOME", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(paths, "PACKAGE_ROOT", tmp_path / "site-packages")
    assert paths.storage_root() == tmp_path / "xdg" / "cpp-risk-analyzer"


def test_cli_path_forms(tiny_repo, monkeypatch):
    """`risk impact` accepts repo-relative, cwd-relative and absolute paths; rejects files outside the repo.
    Req: Interface 1 (CLI usable from the developer's own codebase)
    Expected: all three forms -> "include/lib/core.h"; "nope.h" -> clear error
    """
    from risk_cli import _rel
    repo = tiny_repo.resolve()
    monkeypatch.chdir(repo / "include")
    assert _rel(repo, "lib/core.h") == "include/lib/core.h"            # relative to cwd
    assert _rel(repo, "include/lib/core.h") == "include/lib/core.h"    # relative to repo root
    assert _rel(repo, str(repo / "include/lib/core.h")) == "include/lib/core.h"
    with pytest.raises(typer.BadParameter):
        _rel(repo, "nope.h")
