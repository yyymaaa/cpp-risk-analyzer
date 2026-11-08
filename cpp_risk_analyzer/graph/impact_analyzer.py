import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme


from cpp_risk_analyzer.core import paths

import joblib
import networkx as nx
import pandas as pd

from cpp_risk_analyzer.graph.cochange import CoChangeIndex
from cpp_risk_analyzer.graph.impact_report import compute_report, render
from cpp_risk_analyzer.core.scanner import scan_repository
from cpp_risk_analyzer.core.parser import extract_includes
from cpp_risk_analyzer.graph.graph_builder import build_dependency_graph
from cpp_risk_analyzer.graph.analyzer import StructuralAnalyzer

custom_theme = Theme({
    "info": "#b28dff",
    "success": "bold #ff70a6",
    "warning": "#ffb8d1",
    "error": "bold #ff0a54",
    "highlight": "bold #c77dff"
})

console = Console(theme=custom_theme)

class ChangeImpactAnalyzer:
    """Analyzer potential impact of code changes using trained ML models and graph traversal
    """
    def __init__(self, repo_path: Path | str):
        """Initialized the ChangeImpactAnalyzer with model predictors and dependency graph

        Args:
            repo_path (_type_, optional): Path to the C++ repository under analysis. Defaults to REPO_PATH.
        """
        self.repo_path = Path(repo_path).resolve()
        repo_name = self.repo_path.name

        dataset_path = paths.datasets_dir() / f"{repo_name}_training_dataset.csv"
        model_path = paths.models_dir() / f"{repo_name}_rf_regressor.joblib"

        self.trust = None

        self.has_model = model_path.exists() and dataset_path.exists()

        if self.has_model:
            with console.status(f"[info]Loading ML model ({model_path.name})...[/]", spinner="pong"):
                self.model = joblib.load(model_path)
                self.df = pd.read_csv(dataset_path)

                latest_date = self.df['cutoff_date'].max()
                self.current_state = self.df[self.df['cutoff_date'] == latest_date].copy()

                self.features = [
                    "fan_in", "fan_out", "pagerank", "betweenness",
                    "historical_commit_count_365d", "historical_corrective_count_365d",
                    "historical_cochange_file_count_365d", "historical_cochange_event_count_365d",
                    "days_since_last_change"
                ]
                self.medians = self.current_state[self.features].median()
                self.percentiles_90 = self.current_state[self.features].quantile(0.90)

                self.current_state['predicted_blast_radius'] = self.model.predict(self.current_state[self.features])
                self.current_state = self.current_state.set_index('file_path')
                self.trust = self._load_trust(repo_name)

        else:
            console.print(f"[warning]Notice: Running in Structural Fallback Mode (No ML model available for '{repo_name}').[/]")

        with console.status("[info]Building current structural graph...[/]", spinner="pong"):
            files = scan_repository(self.repo_path)
            dependencies = {f: extract_includes(f) for f in files}
            self.graph = build_dependency_graph(self.repo_path, files, dependencies)

        with console.status("[info]Mining git co-change history...[/]", spinner="pong"):
            self.cochange = CoChangeIndex.mine(self.repo_path, paths.cache_dir())

        # BUG FIX: Unconditionally load the metrics JSON so it is available for fallback lookups
        metrics_file = paths.extraction_dir() / f"{repo_name}_structural_metrics.json"
        if metrics_file.exists():
            with open(metrics_file, "r", encoding="utf-8") as f:
                self.metrics = json.load(f)
        else:
            self.metrics = StructuralAnalyzer(self.graph).calculate_metrics()


    def analyze_impact(self, target_file, show_all=False):
        if target_file not in self.graph.nodes:
            console.print(f"[error]'{target_file}' not found in the structural graph.[/error]")
            return None
        report = compute_report(self, target_file)
        render(report, console, show_all=show_all)
        return report

    def _load_trust(self, repo_name):
        """Model accuracy: saved by train_model.py, or recomputed from the held-out split."""
        f = paths.models_dir() / f"{repo_name}_model_metrics.json"
        try:
            if f.exists():
                return json.loads(f.read_text(encoding="utf-8"))
            import numpy as np
            from sklearn.metrics import mean_squared_error, r2_score
            tr, te = self.df[self.df["split"] == "train"], self.df[self.df["split"] == "test"]
            if te.empty:
                return None
            tgt = "future_cochange_blast_radius_90d"
            pred = self.model.predict(te[self.features])
            return {
                "r2": float(r2_score(te[tgt], pred)),
                "rmse": float(np.sqrt(mean_squared_error(te[tgt], pred))),
                "baseline_rmse": float(np.sqrt(mean_squared_error(te[tgt], np.full(len(te), tr[tgt].mean())))),
                "test_from": str(te["cutoff_date"].min())[:10],
                "test_to": str(te["cutoff_date"].max())[:10],
            }
        except Exception:
            return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run change impact analysis on a target file.")
    parser.add_argument("target_file", type=str, help="Relative path of file to analyze")
    parser.add_argument("--repo", type=Path, required=True, help="Path to target C++ repository")
    args = parser.parse_args()

    analyzer = ChangeImpactAnalyzer(repo_path=args.repo)
    analyzer.analyze_impact(args.target_file)