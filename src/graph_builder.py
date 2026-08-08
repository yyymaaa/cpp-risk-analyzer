from pathlib import Path
import networkx as nx

def build_dependency_graph(
        repository: Path,
        files: list[Path],
        dependencies: dict[Path, list[str]]
) -> nx.DiGraph:
    graph = nx.DiGraph()
    for file in files:
        relative_path = file.relative_to(repository)
        graph.add_node(str(relative_path))

    known_files = {
        file.relative_to(repository).as_posix()
        for file in files
    }

    for file, includes in dependencies.items():
        source = file.relative_to(repository).as_posix()

        for include in includes:
            include_path = Path(include).as_posix()

            if include_path in known_files:
                graph.add_edge(source, include_path)

    return graph