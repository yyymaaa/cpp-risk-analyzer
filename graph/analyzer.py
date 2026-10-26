import networkx as nx
import json
import sys
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

class StructuralAnalyzer:
    """Calculates network structural metrics (Fan-in, Fan-out, PageRank, Betweeness)
for a given code dependency graph
    """    
    def __init__(self, graph: nx.DiGraph):
        """Initializes the Structural Analyzer with a NetworkX directed graph

        Args:
            graph (nx.DiGraph): The directed graph representing file dependencies
        """        
        self.graph = graph


    def calculate_metrics(self) -> Dict[str, Dict[str, float]]:
        """Computes structural metrics for each nodde in thhe dependency graph

        Returns:
            Dict[str, Dict[str, float]]: A dictionary mapping file paths to thheir calculated graph metrics
        """        
        # print("Calculating structural metrics...(This might take a moment)")

        pagerank_scores = nx.pagerank(self.graph)
        betweeness_scores = nx.betweenness_centrality(self.graph)

        file_metrics = {}

        for node in self.graph.nodes():
            in_degree = self.graph.in_degree(node)
            out_degree = self.graph.out_degree(node)

            file_metrics[node] = {
                "fan_in": in_degree,
                "fan_out": out_degree,
                "pagerank": round(pagerank_scores.get(node, 0.0), 6),
                "betweeness_centrality": round(betweeness_scores.get(node, 0.0), 6)
            }

        return file_metrics

    def export_metrics(self, output_path: Path | str | None = None) -> str:
        """Calculates and exports structural metrics to a JSON file

        Args:
            output_path (str, optional): The output path for the JSON file. Defaults to "data/extraction_output/structural_metrics.json".

        Returns:
            str: the output file path where metrics were saved
        """   
        metrics = self.calculate_metrics()
            
        if output_path is None:
            output_path = PROJECT_ROOT / "data" / "extraction_output" / "structural_metrics.json"
        else:
            output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=4)

        return str(output_path)