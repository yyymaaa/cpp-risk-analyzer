import networkx as nx
import json
from typing import Dict

class StructuralAnalyzer:
    def __init__(self, graph: nx.DiGraph):
        self.graph = graph


def calculate_metrics(self) -> Dict[str, Dict[str, float]]:
    print("Calculating structural metrics...(This might take a moment)")

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

def export_metrics(self, output_path: str = "structural_metrics.json") -> str:
    metrics = self.calculate_metrics()

    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=4)

    return output_path