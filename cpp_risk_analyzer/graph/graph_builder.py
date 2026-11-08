from pathlib import Path
import networkx as nx

from cpp_risk_analyzer.core.parser import IncludeDirective
from cpp_risk_analyzer.core.resolver import resolve_include

def build_dependency_graph(
    repository: Path,
    files: list[Path],
    dependencies: dict[Path, list[IncludeDirective]]
) -> nx.DiGraph:
    """Builds a directory graph where nodes are files and edges represent include relationships

    Args:
        repository (Path): The root directory of the repository
        files (list[Path]): A list of source file paths present in the repository
        dependencies (dict[Path, list[IncludeDirective]]): A mapping of source files to their extracted include directives

    Returns:
        nx.DiGraph: A networkX directed graph populated with nodes and dependency edges
    """    
    repository = Path(repository).resolve()   # compare like with like (resolved targets below)
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

            # Absolute includes (e.g. "/usr/include/...") can resolve outside the repo; skip them.
            if result.status == "internal" and result.target.is_relative_to(repository.resolve()):
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