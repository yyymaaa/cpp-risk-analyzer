from pathlib import Path

CPP_EXTENSIONS = {".cpp", ".cc", ".h", ".hpp"}

def scan_repository(root_dir: Path) -> list[Path]:
    cpp_files = []

    for file in root_dir.rglob("*"):
        if file.suffix in CPP_EXTENSIONS:
            cpp_files.append(file)
    return cpp_files