from pathlib import Path
from .parser import IncludeDirective


class ResolutionResult:
    """
    Represents the outcome of an include attempt
    """
    def __init__(
            self, 
            status: str,
            target: Path | None, 
    ) :
        """Initialize a ResolutionResult instance

        Args:
            status (str): The resolution status string
            target (Path | None): The resolved Path Object, or None if unresolved
        """
        self.status = status
        self.target = target

def resolve_include(
        include:IncludeDirective,
        source_file: Path,
        repository: Path,
) -> ResolutionResult:
    """Resolves an include directive to its corresponding file path

    Args:
        include (IncludeDirective): The extracted include directive to resolve
        source_file (Path): The path of the file containing the include
        repository (Path): The root directory of the scanned repository

    Returns:
        ResolutionResult: An object containing the resolution status and resolve path
    """
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
    """Generates a list of potential file paths for include directive

    Args:
        include_path (Path): The path specified in the include directive
        source_file (Path): The path of the file making the inclusion
        repository (Path): The root directory of the scanned repository

    Returns:
        list[Path]: A list of unique candidate Path objects to check for existence
    """
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