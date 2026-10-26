import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent

class GitAnalyzer:
    def __init__(self, repository: Path | str, miner_executable: Path | str | None = None):
        self.repository = Path(repository).resolve()
        repo_name = self.repository.name

        if miner_executable:
            self.miner_executable = Path(miner_executable)
        else:
            self.miner_executable = PROJECT_ROOT / "git_mining" / "git_miner"

        # Default repository-specific output path
        self.default_output = (
            PROJECT_ROOT / "data" / "extraction_output" / f"{repo_name}_commit_log.json"
        )

        
    def extract_history(self) -> List[Dict]:
        if not self.miner_executable.exists():
            print(f"Error: Git miner executable not found at '{self.miner_executable}'.")
            print("Compile it first using: bash git_mining/compile_miner.sh")
            return []

        result = subprocess.run(
            [str(self.miner_executable), str(self.repository)],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                print("Error parsing Git miner output. Ensure the C++ binary compiled correctly.")
                return []
        else:
            print("Git miner execution failed.")
            return []

    def export_history(self, output_path: str = "commit_log.json") -> str:
        target_path = Path(output_path) if output_path else self.default_output
        target_path.parent.mkdir(parents=True, exist_ok=True)

        data = self.extract_history()
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        return str(target_path)