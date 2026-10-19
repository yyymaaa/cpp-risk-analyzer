import json
import subprocess
from pathlib import Path
from typing import Dict, List

import networkx as nx


CPP_SUFFIXES = {".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}


class SemanticAnalyzer:
    def __init__(
        self,
        repository: Path,
        graph: nx.DiGraph,
        parser_executable: str = "./src/semantic_parser",
    ):
        self.repository = Path(repository).resolve()
        self.graph = graph

        executable = Path(parser_executable)
        if not executable.is_absolute():
            executable = Path.cwd() / executable

        self.parser_executable = executable.resolve()

    def extract_semantics(self) -> Dict:
        print("Running native C++ AST parser across repository...")

        if not self.parser_executable.is_file():
            raise FileNotFoundError(
                f"Parser executable not found: {self.parser_executable}"
            )

        semantic_data = {}
        failures = []

        for node in sorted(self.graph.nodes(), key=str):
            relative_source = Path(str(node))
            source_path = (self.repository / relative_source).resolve()

            # Never parse a path outside the repository.
            try:
                relative_source = source_path.relative_to(self.repository)
            except ValueError:
                continue

            if not source_path.is_file():
                continue

            if source_path.suffix.lower() not in CPP_SUFFIXES:
                continue

            result = subprocess.run(
                [
                    str(self.parser_executable),
                    str(source_path),
                    str(self.repository),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                failures.append({
                    "file": relative_source.as_posix(),
                    "error": result.stderr.strip(),
                })
                continue

            try:
                parsed = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                failures.append({
                    "file": relative_source.as_posix(),
                    "error": f"Invalid parser JSON: {exc}",
                })
                continue

            dependencies: List[dict] = []

            for item in parsed.get("dependencies", []):
                if not isinstance(item, dict):
                    continue

                target = item.get("target")
                dep_type = item.get("type")

                if not target or dep_type not in {
                    "inheritance",
                    "function_call",
                }:
                    continue

                raw_target_file = item.get("target_file")
                normalized_target_file = None
                resolution_status = "unresolved"

                if raw_target_file:
                    target_path = Path(raw_target_file)

                    if not target_path.is_absolute():
                        target_path = self.repository / target_path

                    target_path = target_path.resolve()

                    try:
                        normalized_target_file = (
                            target_path.relative_to(self.repository).as_posix()
                        )
                        resolution_status = "internal"
                    except ValueError:
                        # A real declaration was found, but outside this repo.
                        resolution_status = "external"

                dependencies.append({
                    "type": dep_type,
                    "target": target,
                    "target_file": normalized_target_file,
                    "resolution_status": resolution_status,
                })

            source_key = relative_source.as_posix()
            semantic_data[source_key] = dependencies
            self.graph.nodes[node]["semantic_features"] = dependencies

        self.failures = failures

        resolved = sum(
            dep["resolution_status"] == "internal"
            for dependencies in semantic_data.values()
            for dep in dependencies
        )
        unresolved = sum(
            dep["resolution_status"] != "internal"
            for dependencies in semantic_data.values()
            for dep in dependencies
        )

        print(f"Files parsed successfully: {len(semantic_data)}")
        print(f"Dependencies resolved to repository files: {resolved}")
        print(f"External or unresolved dependencies: {unresolved}")
        print(f"Files that failed parsing: {len(failures)}")

        return semantic_data

    def export_semantics(
        self,
        output_path: str = "semantic_dependencies.json",
    ) -> str:
        data = self.extract_semantics()
        output = Path(output_path)

        with output.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)

        if self.failures:
            failure_path = output.with_name(
                output.stem + "_failures.json"
            )
            with failure_path.open("w", encoding="utf-8") as file:
                json.dump(self.failures, file, indent=2)

            print(f"Parser failures recorded in: {failure_path}")

        print(f"Semantic dependencies exported to: {output}")
        return str(output)