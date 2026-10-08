import subprocess
import json
from pathlib import Path
import networkx as nx
from typing import Dict

class SemanticAnalyzer:

    def __init__(self, repository: Path, graph: nx.DiGraph, parser_executable: str = "./src/semantic_parser"):
        self.repository = repository
        self.graph = graph
        self.parser_executable = parser_executable

    def extract_semantics(self) -> Dict:
        print("Running native C++ AST parser across repository...")
        semantic_data = {}

        for node in self.graph.nodes():
            file_path = self.repository / node

            if not file_path.exists() or file_path.suffix not in ['.cc', '.cpp', '.h']:
                continue

            result = subprocess.run(
                [self.parser_executable, str(file_path)],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                try:
                    parsed_json = json.loads(result.stdout)

                    dependencies = [d for d in parsed_json.get("dependencies", []) if d]
                    semantic_data[str(node)] = dependencies

                    self.graph.nodes[node]['semantic_features'] = dependencies

                except json.JSONDecodeError:
                    continue
        return semantic_data

    def export_semantics(self, output_path: str = "semantic_dependencies.json") -> str:
        data = self.extract_semantics()
        with open(output_path, "w") as f:
            json.dump(data, f, indent=4)
        return output_path