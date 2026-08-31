from pathlib import Path
import networkx as nx

from parser import IncludeDirective
from resolver import resolve_include

def build_dependency_graph(
    repository: Path,
    files: list[Path],
    dependencies: dict[Path, list[IncludeDirective]]
) -> nx.DiGraph:
    graph = nx.DiGraph()
    for file in files:
        relative_path = file.relative_to(repository).as_posix()
        graph.add_node(relative_path)

    for source_file, includes in dependencies.items():
        source = source_file.relative_to(repository).as_posix()

        for include in includes:
            result = resolve_include(
                include,
                source_file,
                repository,
            )

            if result.status == "internal":
                target = result.target.relative_to(repository).as_posix()

                graph.add_edge(
                    source,
                    target,
                    relationship="include",
                    line=include.line_number,
                    relationship_type = 'internal',
                    include_path=include.path,
                    delimiter=include.delimiter,
                )

    return graph