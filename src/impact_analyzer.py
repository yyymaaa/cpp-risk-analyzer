import pandas as pd
import numpy as np
import joblib
import networkx as nx
from pathlib import Path
import sys

from scanner import scan_repository
from parser import extract_includes
from graph_builder import build_dependency_graph

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_PATH = Path("/home/ojuka/Desktop/leveldb")
DATASET_PATH = PROJECT_ROOT / "training_dataset.csv"
MODEL_PATH = PROJECT_ROOT / "models" / "random_forest_regressor.joblib"

class ChangeImpactAnalyzer:
    def __init__(self, repo_path=REPO_PATH):
        self.repo_path = Path(repo_path)
        print("Loading ML model and historical dataset...")
        self.model = joblib.load(MODEL_PATH)
        self.df = pd.read_csv(DATASET_PATH)
        
        # Isolate the most recent temporal snapshot to represent the "current" state
        latest_date = self.df['cutoff_date'].max()
        self.current_state = self.df[self.df['cutoff_date'] == latest_date].copy()
        
        # Calculate feature distributions for Explainability (Phase 11)
        self.features = [
            "fan_in", "fan_out", "pagerank", "betweenness",
            "historical_commit_count_365d", "historical_corrective_count_365d",
            "historical_cochange_file_count_365d", "historical_cochange_event_count_365d",
            "days_since_last_change"
        ]
        self.medians = self.current_state[self.features].median()
        self.percentiles_90 = self.current_state[self.features].quantile(0.90)
        
        # Generate predictions for the current state
        self.current_state['predicted_blast_radius'] = self.model.predict(self.current_state[self.features])
        self.current_state.set_index('file_path', inplace=True)

        print("Building current structural graph...")
        files = scan_repository(self.repo_path)
        dependencies = {f: extract_includes(f) for f in files}
        self.graph = build_dependency_graph(self.repo_path, files, dependencies)

    def generate_explanation(self, file_path, row):
        """Phase 11: Generate human-readable per-file explanations"""
        reasons = []
        
        # Check structural risk factors
        if row['pagerank'] > self.percentiles_90['pagerank']:
            reasons.append(f"High Structural Centrality: PageRank is in the top 10% of the codebase.")
        if row['fan_in'] > self.percentiles_90['fan_in']:
            reasons.append(f"High Coupling: {int(row['fan_in'])} other files directly depend on this.")
            
        # Check historical risk factors
        if row['days_since_last_change'] < self.percentiles_90['days_since_last_change']:
            # Since low days = recently changed, this is a volatility indicator
            if row['historical_commit_count_365d'] > self.medians['historical_commit_count_365d']:
                reasons.append(f"Historical Volatility: Highly active recently with {int(row['historical_commit_count_365d'])} commits in the last year.")
        if row['historical_cochange_file_count_365d'] > self.percentiles_90['historical_cochange_file_count_365d']:
            reasons.append(f"Ripple Effect: Historically triggers widespread co-changes when modified.")

        if not reasons:
            reasons.append("Standard risk profile. No extreme structural or historical outliers detected.")
            
        return reasons

    def analyze_impact(self, target_file):
        """Phase 12: Change-Impact Analysis via Graph Traversal"""
        if target_file not in self.graph.nodes:
            print(f"Error: {target_file} not found in the structural graph.")
            return

        # In our graph, A -> B means A includes B. 
        # Therefore, files that depend on B are B's ancestors.
        dependents = list(nx.ancestors(self.graph, target_file))
        
        print(f"\n{'='*60}")
        print(f"CHANGE IMPACT REPORT: {target_file}")
        print(f"{'='*60}")
        print(f"Direct & Transitive Dependents Found: {len(dependents)}")
        
        impacted_files = []
        for dep in dependents:
            if dep in self.current_state.index:
                row = self.current_state.loc[dep]
                impacted_files.append({
                    'file': dep,
                    'risk_score': row['predicted_blast_radius'],
                    'explanation': self.generate_explanation(dep, row)
                })

        if not impacted_files:
            print("No modeled dependents found. This file is likely a leaf node or standalone utility.")
            return

        # Sort by ML Predicted Risk (Highest First)
        impacted_files.sort(key=lambda x: x['risk_score'], reverse=True)
        
        print("\nTOP RISK HOTSPOTS TO TEST/REVIEW:")
        for idx, item in enumerate(impacted_files[:10], 1): # Show top 10
            print(f"\n{idx}. {item['file']}")
            print(f"   Predicted Blast Radius: {item['risk_score']:.2f} files")
            for reason in item['explanation']:
                print(f"   * {reason}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/impact_analyzer.py <file_path_relative_to_repo>")
        print("Example: python src/impact_analyzer.py util/hash.cc")
        sys.exit(1)
        
    target = sys.argv[1]
    analyzer = ChangeImpactAnalyzer()
    analyzer.analyze_impact(target)