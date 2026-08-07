from pathlib import Path
import sys

from scanner import scan_repository
from parser import extract_includes

if len(sys.argv) < 2:
    print("Usage:")
    print("python main.py <repository>")
    sys.exit(1)

repository = Path(sys.argv[1])

if not repository.is_dir():
    print("Invalid repository.")
    sys.exit(1)

files = scan_repository(repository)

for file in files:
    includes = extract_includes(file)
    print(file.relative_to(repository))

    for include in includes:
        print("   ->", include)

    print()

    