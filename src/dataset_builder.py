import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from historical_graph import historical_graph
from analyzer import StructuralAnalyzer


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_PATH = Path("/home/ojuka/Desktop/leveldb")

LOOKBACK_DAYS = 365
HORIZON_DAYS = 90
STEP_DAYS = 90

CORRECTIVE_PATTERN = re.compile(
    r"\b(?:fix(?:es|ed|ing)?|bug(?:s|fix(?:es)?)?|"
    r"crash(?:es|ed)?|leak(?:s|ed)?|race(?:s)?|"
    r"regress(?:es|ed|ion|ions)?|revert(?:s|ed)?)\b",
    re.IGNORECASE,
)

COMMIT_HEADER = re.compile(r"^([0-9a-f]{40})\t(\d+)\t(.*)$")


def numeric_metric(metrics, name):
    """Return a numeric structural metric, defaulting to zero if absent."""
    value = metrics.get(name, 0) if isinstance(metrics, dict) else 0

    try:
        value = float(value)
        return value if pd.notna(value) else 0.0
    except (TypeError, ValueError):
        return 0.0


class TemporalDatasetBuilder:
    def __init__(self, repo_path=REPO_PATH):
        self.repo_path = Path(repo_path)
        self.structural_path = PROJECT_ROOT / "structural_metrics.json"
        self.output_path = PROJECT_ROOT / "training_dataset.csv"

        if not self.repo_path.is_dir():
            raise FileNotFoundError(
                f"Git repository not found: {self.repo_path}"
            )

        if not self.structural_path.is_file():
            raise FileNotFoundError(
                f"Structural metrics not found: {self.structural_path}"
            )

        with self.structural_path.open() as f:
            self.structural = json.load(f)

        if not isinstance(self.structural, dict) or not self.structural:
            raise ValueError("Structural metrics JSON is empty or invalid.")

        self.current_files = set(self.structural)

    def read_git_history(self):
        """Read commit timestamps, subjects and changed paths from HEAD."""
        result = subprocess.run(
            [
                "git", "log",
                "--format=%H%x09%ct%x09%s",
                "--name-only",
                "--no-renames",
                "HEAD",
            ],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
            text=True,
        )

        commits = []
        current = None

        def save_current():
            if current is not None:
                current["files"] = set(current["files"])
                current["corrective"] = bool(
                    CORRECTIVE_PATTERN.search(current["subject"])
                )
                commits.append(current.copy())

        for line in result.stdout.splitlines():
            match = COMMIT_HEADER.match(line)

            if match:
                save_current()
                current = {
                    "id": match.group(1),
                    "timestamp": int(match.group(2)),
                    "subject": match.group(3),
                    "files": set(),
                }
            elif current is not None and line.strip():
                current["files"].add(line.strip())

        save_current()

        # Preserve the existing label/activity scope for this iteration.
        for commit in commits:
            commit["files"] &= self.current_files

        commits = [c for c in commits if c["files"]]
        commits.sort(key=lambda c: (c["timestamp"], c["id"]))

        if not commits:
            raise ValueError(
                "No Git commits matched the current structural file paths."
            )

        return commits

    def build(self, output_path=None):
        commits = self.read_git_history()

        lookback = LOOKBACK_DAYS * 86400
        horizon = HORIZON_DAYS * 86400
        step = STEP_DAYS * 86400

        first_timestamp = min(c["timestamp"] for c in commits)
        last_timestamp = max(c["timestamp"] for c in commits)

        first_cutoff = first_timestamp + lookback
        last_cutoff = last_timestamp - horizon

        if first_cutoff >= last_cutoff:
            raise ValueError(
                "Insufficient Git history for the chosen lookback and horizon."
            )

        cutoffs = list(range(first_cutoff, last_cutoff + 1, step))

        if len(cutoffs) < 5:
            raise ValueError(
                f"Only {len(cutoffs)} snapshots available; "
                "at least five are required for a chronological split."
            )

        first_seen = {}
        for commit in commits:
            for path in commit["files"]:
                first_seen[path] = min(
                    first_seen.get(path, commit["timestamp"]),
                    commit["timestamp"],
                )

        rows = []
        snapshots_built = 0

        for cutoff in cutoffs:
            history_start = cutoff - lookback
            future_end = cutoff + horizon

            history = [
                c for c in commits
                if history_start < c["timestamp"] <= cutoff
            ]
            future_corrective = [
                c for c in commits
                if cutoff < c["timestamp"] <= future_end
                and c["corrective"]
            ]

            # Reconstruct structural features as of this exact cutoff.
            commit_id, graph = historical_graph(
                self.repo_path, cutoff
            )
            metrics_by_path = StructuralAnalyzer(
                graph
            ).calculate_metrics()
            snapshots_built += 1

            print(
                f"Snapshot {snapshots_built}/{len(cutoffs)}: "
                f"{datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()} "
                f"commit={commit_id[:12]} "
                f"nodes={graph.number_of_nodes()}"
            )

            file_commits = defaultdict(int)
            file_corrective = defaultdict(int)
            file_cochanges = defaultdict(set)
            file_cochange_events = defaultdict(int)
            last_change = {}

            for commit in history:
                files = commit["files"]

                for path in files:
                    file_commits[path] += 1
                    last_change[path] = max(
                        last_change.get(path, 0),
                        commit["timestamp"],
                    )

                    if commit["corrective"]:
                        file_corrective[path] += 1

                    for other in files:
                        if other != path:
                            file_cochanges[path].add(other)
                            file_cochange_events[path] += 1

            future_positive = set()
            for commit in future_corrective:
                future_positive.update(commit["files"])

            cutoff_date = datetime.fromtimestamp(
                cutoff, tz=timezone.utc
            ).date().isoformat()

            for path in sorted(self.current_files):
                if first_seen.get(path, last_timestamp + 1) > cutoff:
                    continue

                # A current file may not exist in this historical snapshot.
                # Do not assign it structural metrics from today's graph.
                metrics = metrics_by_path.get(path)
                if metrics is None:
                    continue

                previous_change = last_change.get(path)

                rows.append({
                    "file_path": path,
                    "cutoff_date": cutoff_date,
                    "fan_in": numeric_metric(metrics, "fan_in"),
                    "fan_out": numeric_metric(metrics, "fan_out"),
                    "pagerank": numeric_metric(metrics, "pagerank"),
                    "betweenness": numeric_metric(
                        metrics, "betweeness_centrality"
                    ),
                    "historical_commit_count_365d": file_commits[path],
                    "historical_corrective_count_365d": file_corrective[path],
                    "historical_cochange_file_count_365d": len(
                        file_cochanges[path]
                    ),
                    "historical_cochange_event_count_365d":
                        file_cochange_events[path],
                    "days_since_last_change": (
                        min(
                            LOOKBACK_DAYS,
                            (cutoff - previous_change) // 86400,
                        )
                        if previous_change is not None
                        else LOOKBACK_DAYS
                    ),
                    "future_corrective_change_90d": int(
                        path in future_positive
                    ),
                })

        if not rows:
            raise ValueError(
                "No dataset rows were generated. Check historical paths "
                "and graph reconstruction."
            )

        df = pd.DataFrame(rows)

        unique_dates = sorted(df["cutoff_date"].unique())
        if len(unique_dates) < 2:
            raise ValueError(
                "At least two distinct snapshot dates are required to split."
            )

        split_index = max(1, int(len(unique_dates) * 0.8))
        split_index = min(split_index, len(unique_dates) - 1)
        test_start = unique_dates[split_index]

        df["split"] = df["cutoff_date"].map(
            lambda d: "test" if d >= test_start else "train"
        )

        destination = (
            Path(output_path) if output_path is not None
            else self.output_path
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(destination, index=False)

        print(f"\nGit commits parsed: {len(commits)}")
        print(f"Current structural files: {len(self.current_files)}")
        print(f"Temporal snapshots built: {snapshots_built}")
        print(f"Snapshots represented in dataset: {len(unique_dates)}")
        print(f"Dataset rows: {len(df)}")
        print(f"Distinct files represented: {df['file_path'].nunique()}")
        print(f"Training rows: {(df['split'] == 'train').sum()}")
        print(f"Test rows: {(df['split'] == 'test').sum()}")
        print(
            "Positive training labels:",
            int(df.loc[
                df["split"] == "train",
                "future_corrective_change_90d"
            ].sum()),
        )
        print(
            "Positive test labels:",
            int(df.loc[
                df["split"] == "test",
                "future_corrective_change_90d"
            ].sum()),
        )
        print(f"Test period starts: {test_start}")
        print(f"Saved dataset: {destination}")

        print("\nLabel distribution by split:")
        print(pd.crosstab(
            df["split"], df["future_corrective_change_90d"]
        ))

        return df


if __name__ == "__main__":
    TemporalDatasetBuilder().build()

