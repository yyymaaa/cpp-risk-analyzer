import io
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

from scanner import scan_repository
from parser import extract_includes
from graph_builder import build_dependency_graph
from analyzer import StructuralAnalyzer


def git_output(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def historical_graph(
    repo: Path, cutoff_timestamp: int
) -> tuple[str, nx.DiGraph]:
    """Build an include-dependency graph from the latest eligible first-parent commit."""
    repo = repo.resolve()

    cutoff_date = datetime.fromtimestamp(
        cutoff_timestamp, tz=timezone.utc
    ).isoformat()

    commit = git_output(
        repo,
        "log",
        "-1",
        "--first-parent",
        f"--before=@{cutoff_timestamp}",
        "--format=%H",
        "HEAD",
    ).strip()

    if not commit:
        raise ValueError(
            f"No commit found on or before {cutoff_date}"
        )

    # Use a temporary directory; never check out or modify the real repository.
    with tempfile.TemporaryDirectory(
        prefix="cpp-risk-history-"
    ) as tmp:
        snapshot = Path(tmp)

        archive = subprocess.run(
            ["git", "archive", commit],
            cwd=repo,
            capture_output=True,
            check=True,
        )

        with tarfile.open(
            fileobj=io.BytesIO(archive.stdout), mode="r:"
        ) as tar:
            tar.extractall(snapshot, filter="data")

        files = scan_repository(snapshot)

        dependencies = {
            file: extract_includes(file)
            for file in files
        }

        graph = build_dependency_graph(
            snapshot, files, dependencies
        )
        graph = nx.DiGraph(graph)

        graph.graph["commit"] = commit
        graph.graph["cutoff_timestamp"] = cutoff_timestamp
        graph.graph["cutoff_date"] = cutoff_date
        graph.graph["source_file_count"] = len(files)

        return commit, graph


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: python src/historical_graph.py "
            "<repository> <cutoff_unix_timestamp>"
        )

    repository = Path(sys.argv[1])
    cutoff = int(sys.argv[2])

    commit, graph = historical_graph(repository, cutoff)
    metrics = StructuralAnalyzer(graph).calculate_metrics()

    print(f"Cutoff date: {graph.graph['cutoff_date']}")
    print(f"Cutoff timestamp: {cutoff}")
    print(f"Selected commit: {commit}")
    print(
        f"Source files scanned: "
        f"{graph.graph['source_file_count']}"
    )
    print(f"Graph nodes: {graph.number_of_nodes()}")
    print(f"Graph edges: {graph.number_of_edges()}")
    print(f"Metrics calculated: {len(metrics)}")

    print("\nSample metrics:")
    for path, values in list(metrics.items())[:5]:
        print(path, values)

