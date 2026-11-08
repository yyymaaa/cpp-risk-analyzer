from cpp_risk_analyzer.core.parser import IncludeDirective, extract_includes
from cpp_risk_analyzer.core.scanner import scan_repository
from cpp_risk_analyzer.graph.analyzer import StructuralAnalyzer
from cpp_risk_analyzer.graph.graph_builder import build_dependency_graph
from cpp_risk_analyzer.graph.validator import GraphValidator


def _graph(repo):
    files = scan_repository(repo)
    return build_dependency_graph(repo, files, {f: extract_includes(f) for f in files})


def test_graph_nodes_and_edges(tiny_repo):
    """Dependency graph has one node per file and one edge per internal include.
    Req: FR3
    Expected: 7 nodes; 6 edges (dependent -> dependency); no edges to system headers
    """
    g = _graph(tiny_repo)
    assert g.number_of_nodes() == 7
    assert set(g.edges()) == {
        ("include/lib/util.h", "include/lib/core.h"), ("include/lib/api.h", "include/lib/core.h"),
        ("src/engine.cc", "include/lib/util.h"), ("src/api.cc", "include/lib/api.h"),
        ("tests/core_test.cc", "include/lib/core.h"), ("tools/cli.cc", "include/lib/api.h"),
    }


def test_absolute_include_outside_repo_ignored(tiny_repo, tmp_path):
    """An absolute include pointing outside the repository adds no edge and does not crash.
    Req: FR3, robustness (regression test for the RocksDB /usr/include/valgrind crash)
    Expected: graph builds; no edge to the outside file
    """
    outside = tmp_path / "outside.h"
    outside.write_text("int x;")
    files = scan_repository(tiny_repo)
    deps = {f: extract_includes(f) for f in files}
    deps[tiny_repo / "src/engine.cc"].append(IncludeDirective(str(outside), '"', 99))
    g = build_dependency_graph(tiny_repo, files, deps)
    assert all(str(outside) not in e[1] for e in g.edges())


def test_structural_metrics(tiny_repo):
    """Fan-in, fan-out and PageRank are computed for every file.
    Req: FR3
    Expected: core.h fan_in 3 and highest PageRank; engine.cc fan_out 1, fan_in 0
    """
    m = StructuralAnalyzer(_graph(tiny_repo)).calculate_metrics()
    assert m["include/lib/core.h"]["fan_in"] == 3
    assert (m["src/engine.cc"]["fan_out"], m["src/engine.cc"]["fan_in"]) == (1, 0)
    assert max(m, key=lambda k: m[k]["pagerank"]) == "include/lib/core.h"


def test_validator_counts_and_cycles(tiny_repo):
    """Validator reports correct node/edge counts and detects circular dependencies.
    Req: FR3
    Expected: 7 nodes, 6 edges, 0 cycles; after adding core.h -> util.h: 1 cycle
    """
    g = _graph(tiny_repo)
    s = GraphValidator(g).run_structural_checks()
    assert (s["node_count"], s["edge_count"], s["cyclic_dependencies_count"]) == (7, 6, 0)
    g.add_edge("include/lib/core.h", "include/lib/util.h")
    assert GraphValidator(g).run_structural_checks()["cyclic_dependencies_count"] == 1
