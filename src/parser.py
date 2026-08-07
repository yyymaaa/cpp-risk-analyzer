from pathlib import Path

def extract_includes(file_path: Path) -> list[str]:
    includes = []

    with file_path.open("r", encoding="utf-8", errors="ignore") as file:
        for line in file:
            line = line.strip()

            if line.startswith('"#include "'): # " because of lines like #include <vector>, we do not want to extract that
                parts = line.split('"')

                if len(parts) >= 2:
                    includes.append(parts[1])
    return includes