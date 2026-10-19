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

def scan_repository(repository: Path) -> list[Path]:
    """Recursively scan a repository for C++ source and header files

    Args:
        repository (Path): The root directory path of the repository to scan

    Returns:
        list[Path]: A sorted list of Path objects for the discovered C++ files
    """    
    found_files = [
        path
        for path in repository.rglob("*")
        if path.is_file() and path.suffix.lower() in CPP_EXTENSIONS
    ]

    return sorted(found_files)

