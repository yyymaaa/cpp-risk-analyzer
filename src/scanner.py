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
    found_files = [
        path
        for path in repository.rglob("*")
        if path.is_file() and path.suffix.lower() in CPP_EXTENSIONS
    ]

    return sorted(found_files)

"""

    cpp_files = []

    for file in root_dir.rglob("*"):
        if file.suffix in CPP_EXTENSIONS:
            cpp_files.append(file)
    return cpp_files

"""