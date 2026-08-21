from pathlib import Path
from parser import IncludeDirective


class ResolutionResult:
    def __init__(
            self, 
            status: str,
            target: Path | None, 
    ) :
        self.status = status
        self.target = target

def resolve_include(
        include:IncludeDirective,
        source_file: Path,
        repository: Path,
) -> ResolutionResult:
    include_path = Path(include.path)

    if include.delimiter == "<":
        candidate_paths = _candidate_paths(
            include_path,
            source_file,
            repository,
        )

        for candidate in candidate_paths:
            if candidate.is_file():
                return ResolutionResult(
                    status = "internal",
                    target = candidate.resolve(),
                )

        return ResolutionResult(
            status="external",
            target=None,
        )

    candidate_paths = _candidate_paths(
        include_path,
        source_file,
        repository,
    )

    for candidate in candidate_paths:
        if candidate.is_file():
            return ResolutionResult(
                status="internal",
                target=candidate.resolve(),
            )

    return ResolutionResult(
        status="unresolved",
        target=None,
    )

def _candidate_paths(
        include_path: Path,
        source_file: Path,
        repository: Path,
) -> list[Path]:
    candidates:list[Path] = []

    candidates.append(
        source_file.parent / include_path
    )

    candidates.append(
        repository / include_path
    )

    candidates.append(
        repository / "include" / include_path
    )

    candidates.append(
        repository / "src" / include_path
    )

    unique_candidates = []

    seen = set()

    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique_candidates.append(candidate)

    return unique_candidates