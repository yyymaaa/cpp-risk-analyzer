from pathlib import Path
import sys
import json

from scanner import scan_repository
from parser import extract_includes
from graph_builder import build_dependency_graph
from validator import GraphValidator

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



    