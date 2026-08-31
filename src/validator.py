import networkx as nx
import json
from typing import Dict, Any

class GraphValidator:
    def __init__(self, graph: nx.DiGraph):
        self.graph = graph
    def calculate_resolution_metrics(self) -> Dict[str, Any]:
        total_edges = self.graph.number_of_edges()
        internal_resolved = sum(
            1 for u, v, data in self.graph.edges(data=True)
            if data.get('relationship_type') == 'internal'
        )

        resolution_rate = (internal_resolved / total_edges) if total_edges > 0 else 0.0

        return {
            "total_itnernal_edges" : internal_resolved,
            "resolution_rate": round(resolution_rate, 4)
        }

    def run_structural_checks(self) -> Dict[str, Any]:
        isolates = list(nx.isolates(self.graph))
        self_loops = list(nx.selfloop_edges(self.graph))
        weak_components = list(nx.weakly_connected_components(self.graph))
        sccs = [c for c in nx.strongly_connected_components(self.graph) if len(c) > 1]
        density = nx.density(self.graph)

        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_nodes(),
            "isolated_nodes_count": len(isolates),
            "self_loop_count": len(self_loops),
            "disconnected_subgraphs": len(weak_components),
            "cyclic_dependencies_count": len(sccs),
            "graph_density": round(density, 6)
        }

    def generate_report(self) -> str:
        report = {
            "resolution_metrics": self.calculate_resolution_metrics(),
            "structural_health": self.run_structural_checks()
        }
        return json.dumps(report, indent=4)

