from pathlib import Path
import sys

if len(sys.argv) < 2:
    print("Try: python traverseDir.py <directory_path>")
    sys.exit(1)

rootDir = Path(sys.argv[1])

if not rootDir.is_dir():
    print(f"Error: {rootDir} is not a valid directory")
    sys.exit(1)


found_files = rootDir.rglob("*") # this means go deep into every folder you find

for file in found_files:
    if file.suffix == ".cpp" or file.suffix == ".h" or file.suffix == ".cc":
        print(file.relative_to(rootDir))