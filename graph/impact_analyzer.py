import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import networkx as nx
import pandas as pd

from core.scanner import scan_repository
from core.parser import extract_includes
from graph.graph_builder import build_dependency_graph
from graph.analyzer import StructuralAnalyzer

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

        dataset_path = PROJECT_ROOT / "data" / "ml_datasets" / f"{repo_name}_training_dataset.csv"
        model_path = PROJECT_ROOT / "models" / f"{repo_name}_rf_regressor.joblib"

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
                self.current_state.set_index('file_path', inplace=True)
        else:
            console.print(f"[warning]Notice: Running in Structural Fallback Mode (No ML model available for '{repo_name}').[/]")

        with console.status("[info]Building current structural graph...[/]", spinner="pong"):
            files = scan_repository(self.repo_path)
            dependencies = {f: extract_includes(f) for f in files}
            self.graph = build_dependency_graph(self.repo_path, files, dependencies)

        # BUG FIX: Unconditionally load the metrics JSON so it is available for fallback lookups
        metrics_file = PROJECT_ROOT / "data" / "extraction_output" / f"{repo_name}_structural_metrics.json"
        if metrics_file.exists():
            with open(metrics_file, "r") as f:
                self.metrics = json.load(f)
        else:
            self.metrics = StructuralAnalyzer(self.graph).calculate_metrics()

    def generate_explanation(self, file_path, row):
        """Generates human-readable explanation messages per file based on feature thresholds

        Args:
            file_path (_type_): Relative file path being evaluated
            row (_type_): Dataset row containing metrics for the specified file

        Returns:
            _type_: Explanatory statements identifying structural or historical risk factors
        """        
        """Phase 11: Generate human-readable per-file explanations"""
        reasons = []
        
        # Check structural risk factors
        reasons = []
        
        if row['pagerank'] > self.percentiles_90['pagerank']:
            reasons.append("High Structural Centrality: PageRank is in top 10% of codebase.")
        if row['fan_in'] > self.percentiles_90['fan_in']:
            reasons.append(f"High Coupling: {int(row['fan_in'])} other files directly depend on this.")

        if row['days_since_last_change'] < self.percentiles_90['days_since_last_change']:
            if row['historical_commit_count_365d'] > self.medians['historical_commit_count_365d']:
                reasons.append(f"Historical Volatility: Active recently with {int(row['historical_commit_count_365d'])} commits in last year.")
        
        if row['historical_cochange_file_count_365d'] > self.percentiles_90['historical_cochange_file_count_365d']:
            reasons.append("Ripple Effect: Historically triggers widespread co-changes when modified.")

        if not reasons:
            reasons.append("Standard risk profile.")

        return reasons

    def analyze_impact(self, target_file):
        """Perform change-impact analysis for a target file via graph traversal and ML scoring

        Args:
            target_file (_type_): relative file path within the repository to analyze
        """        
        if target_file not in self.graph.nodes:
            console.print(f"[error]Error: '{target_file}' not found in the structural graph.[/error]")
            return

        dependents = list(nx.ancestors(self.graph, target_file))
        mode_text = "Machine Learning Predicted Risk" if self.has_model else "Structural Centrality Fallback"

        # Styled Banner
        banner_text = Text(f"CHANGE IMPACT REPORT", style="bold #ff70a6", justify="center")
        banner_text.append(f"\nTarget: {target_file}", style="#c77dff")
        banner_text.append(f"\nMode: {mode_text}", style="#b28dff")
        banner_text.append(f"\nDirect & Transitive Dependents: {len(dependents)}", style="bold white")
        console.print(Panel(banner_text, border_style="#b28dff", padding=(1, 2)))

        impacted_files = []
        for dep in dependents:
            if self.has_model and dep in self.current_state.index:
                row = self.current_state.loc[dep]
                impacted_files.append({
                    'file': dep,
                    'risk_score': row['predicted_blast_radius'],
                    'label': 'Predicted Blast Radius',
                    'explanation': self.generate_explanation(dep, row)
                })
            else:
                node_metrics = self.metrics.get(dep, {})
                fan_in = node_metrics.get("fan_in", 0)
                pagerank = node_metrics.get("pagerank", 0.0)

                struct_score = (pagerank * 10.0) + fan_in
                reasons = []
                if fan_in > 0:
                    reasons.append(f"Structural Coupling: {fan_in} dependent file(s).")
                if pagerank > 0.01:
                    reasons.append(f"High Structural Centrality: PageRank = {pagerank:.4f}.")
                if not reasons:
                    reasons.append("Leaf node in dependency graph.")

                impacted_files.append({
                    'file': dep,
                    'risk_score': struct_score,
                    'label': 'Structural Risk Score',
                    'explanation': reasons
                })

        if not impacted_files:
            console.print("[info]No dependents found. This file is a leaf node.[/]")
            return

        impacted_files.sort(key=lambda x: x['risk_score'], reverse=True)

        # Styled Table for Hotspots
        table = Table(title="Top Risk Hotspots to Test / Review", border_style="#b28dff", header_style="bold #ff70a6", title_style="bold #c77dff")
        table.add_column("Dependent File", style="bold white")
        table.add_column("Risk Score", justify="right", style="#c77dff")
        table.add_column("Key Drivers", style="#b28dff")

        for item in impacted_files[:10]:
            drivers = "\n".join([f"• {reason}" for reason in item['explanation']])
            table.add_row(item['file'], f"{item['risk_score']:.2f}", drivers)
            table.add_row("", "", "") # Add spacing between entries

        console.print(table)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run change impact analysis on a target file.")
    parser.add_argument("target_file", type=str, help="Relative path of file to analyze")
    parser.add_argument("--repo", type=Path, required=True, help="Path to target C++ repository")
    args = parser.parse_args()

    analyzer = ChangeImpactAnalyzer(repo_path=args.repo)
    analyzer.analyze_impact(args.target_file)