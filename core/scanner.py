from pathlib import Path

CPP_EXTENSIONS = {
    ".cpp", 
    ".cc",
    ".cxx",
    ".hh", 
    ".h", 
    ".hpp",
    ".hxx"
}

DEFAULT_IGNORE_DIRS = {
    "third-party",
    "thirdparty",
    "3rdparty",
    "vendor",
    "deps",
    "external",
    "externals",
    "googletest",
    "gtest",
    "benchmark",
    "build",
    "cmake-build-debug",
    "cmake-build-release",
    ".git"
}

def scan_repository(repository: Path, ignore_dirs: set[str] | None = None) -> list[Path]:
    """Recursively scan a repository for C++ source and header files

    Args:
        repository (Path): The root directory path of the repository to scan

    Returns:
        list[Path]: A sorted list of Path objects for the discovered C++ files
    """    
    repository = Path(repository).resolve()
    ignored = ignore_dirs if ignore_dirs is not None else DEFAULT_IGNORE_DIRS

    found_files = []

    for path in repository.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in CPP_EXTENSIONS:
            continue

        # Get path parts relative to repository root (e.g. ['third-party', 'gtest', 'gtest.h'])
        rel_parts = path.relative_to(repository).parts

        # Skip if any segment in the path belongs to an ignored directory
        if any(part.lower() in ignored for part in rel_parts):
            continue

        found_files.append(path)

    return sorted(found_files)
