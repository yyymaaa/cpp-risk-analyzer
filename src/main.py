from pathlib import Path
import sys
import json

from scanner import scan_repository
from parser import extract_includes
from graph_builder import build_dependency_graph
from validator import GraphValidator
from analyzer import StructuralAnalyzer
from semantic_analyzer import SemanticAnalyzer
from git_analyzer import GitAnalyzer
from db_loader import DatabaseLoader

if len(sys.argv) < 2:
    print("Usage:")
    print("python src/main.py <repository>")
    sys.exit(1)

repository = Path(sys.argv[1]).resolve()

if not repository.is_dir():
    print(f"Error: {repository} is not a valid directory")
    sys.exit(1)

files = scan_repository(repository)
print(f"Found {len(files)} C++ files.")

dependencies = {}
total_includes = 0

for file in files:
    includes = extract_includes(file)
    dependencies[file] = includes
    total_includes += len(includes)

print(f"Found {total_includes} include directives.")

graph = build_dependency_graph(
    repository,
    files,
    dependencies
)

print(f"Graph contains {graph.number_of_nodes()} nodes.")
print(f"Graph contains {graph.number_of_edges()} edges.")

print("\nSample dependency relationships:")

for source, target, data in list(graph.edges(data=True))[:20]:
    print(
        f"{source} -> {target}"
        f"(line {data['line']})"
    )

print("Graph Validation")
validator = GraphValidator(graph)
report = validator.generate_report()
print(report)

print("\nStructural Dependency Analysis")
analyzer = StructuralAnalyzer(graph)
output_file = analyzer.export_metrics()
print(f"Success! Structural metrics exported to: {output_file}")

print("\nSemantic C++ Dependency Analysis")
semantic_analyzer = SemanticAnalyzer(repository, graph)
semantic_output = semantic_analyzer.export_semantics()
print(f"Success! Semantic features exported to: {semantic_output}")

print("\nHistorical Git Mining")
git_analyzer = GitAnalyzer(repository)
git_output = git_analyzer.export_history()
print(f"Success! Raw commit log exported to: {git_output}")

print("\nMySQL Ingestion Layer")
db_loader = DatabaseLoader()
db_loader.load_structural_data()
db_loader.load_semantic_data()
db_loader.load_git_data()
db_loader.close()
print("Success! All JSON artifacts normalized and ingested into MySQL.")