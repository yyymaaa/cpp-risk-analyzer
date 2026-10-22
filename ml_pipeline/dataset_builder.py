import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from graph.historical_graph import historical_graph
from graph.analyzer import StructuralAnalyzer

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
    """extract a numeric structural metric from a dictionary with fallback handling

    Args:
        metrics (_type_): Dictionary containing node metrics
        name (_type_): Key name of the metrics to retrieve

    Returns:
        _type_: Calculated metric vaue as float, or 0.0 if absent or invalid
    """    
    """Return a numeric structural metric, defaulting to zero if absent."""
    value = metrics.get(name, 0) if isinstance(metrics, dict) else 0

    try:
        value = float(value)
        return value if pd.notna(value) else 0.0
    except (TypeError, ValueError):
        return 0.0


class TemporalDatasetBuilder:
    """builds temporal training dataset combining historical git commit churn and graph
    centralitry metrics across rolling window cutoffs
    """    
    def __init__(self, repo_path=REPO_PATH):
        """initialized the dataset builder with target repository path and structural baselines

        Args:
            repo_path (_type_, optional): Path to the target Git repository under analysis. Defaults to REPO_PATH.

        Raises:
            FileNotFoundError: if the repo or structural metrics file does not exist
            ValueError: If the structural metrics JSON format is invalid
        """        
        self.repo_path = Path(repo_path).resolve()
        repo_name = self.repo_path.name

        if not self.repo_path.is_dir():
            raise FileNotFoundError(
                f"Git repository not found: {self.repo_path}"
            )

        # Dynamic repository-specific extraction and output paths
        self.structural_path = PROJECT_ROOT / "data" / "extraction_output" / f"{repo_name}_structural_metrics.json"
        if not self.structural_path.exists():
            self.structural_path = PROJECT_ROOT / "data" / "extraction_output" / "structural_metrics.json"

        self.output_path = PROJECT_ROOT / "data" / "ml_datasets" / f"{repo_name}_training_dataset.csv"

        with self.structural_path.open() as f:
            self.structural = json.load(f)

        if not isinstance(self.structural, dict) or not self.structural:
            raise ValueError("Structural metrics JSON is empty or invalid.")

        self.current_files = set(self.structural)

    def read_git_history(self):
        """parses commit history, timestamps, messages and affected paths from Git log

        Raises:
            ValueError: If no git commits match current codebase file paths

        Returns:
            _type_: list of parsed commit records matched against active structural paths
        """        
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
        """generates rollimh temoral snapshots, computed features columns, and saves the CSV dataset

        Args:
            output_path (_type_, optional): Custom target destination for CSV dataset export. Defaults to None.

        Raises:
            ValueError: If commit history or temporal snapshot constraints are not met
            

        Returns:
            _type_: formatted dataset containing temporal features and target blast radius
        """        
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
            
            # Path A: Look at all future commits to measure true change propagation,
            # dropping the noisy "corrective" keyword filter entirely.
            future_commits = [
                c for c in commits
                if cutoff < c["timestamp"] <= future_end
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

            # Path A: Calculate continuous blast radius (co-change impact)
            future_cochange_impact = defaultdict(set)
            for commit in future_commits:
                files = commit["files"]
                for path in files:
                    # Add all OTHER files in this commit to the impacted set for `path`
                    future_cochange_impact[path].update(f for f in files if f != path)

            cutoff_date = datetime.fromtimestamp(
                cutoff, tz=timezone.utc
            ).date().isoformat()

            for path in sorted(self.current_files):
                if first_seen.get(path, last_timestamp + 1) > cutoff:
                    continue

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
                    # Target is now a continuous integer instead of 0 or 1
                    "future_cochange_blast_radius_90d": len(future_cochange_impact.get(path, set())),
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
        print(f"Dataset rows: {len(df)}")
        
        train_df = df[df["split"] == "train"]
        test_df = df[df["split"] == "test"]
        
        print(f"Training rows: {len(train_df)}")
        print(f"Test rows: {len(test_df)}")
        print(f"Mean train blast radius: {train_df['future_cochange_blast_radius_90d'].mean():.2f}")
        print(f"Mean test blast radius: {test_df['future_cochange_blast_radius_90d'].mean():.2f}")
        print(f"Saved dataset: {destination}")

        return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build temporal dataset for a C++ repository.")
    parser.add_argument("repo_path", type=Path, help="Path to target C++ repository")
    args = parser.parse_args()

    TemporalDatasetBuilder(repo_path=args.repo_path).build()
