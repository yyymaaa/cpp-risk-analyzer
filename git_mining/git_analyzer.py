import subprocess
import json
from pathlib import Path
from typing import List, Dict

class GitAnalyzer:
    def __init__(self, repository: Path, miner_executable: str = "./src/git_miner"):
        self.repository = repository
        self.miner_executable = miner_executable

    def extract_history(self) -> List[Dict]:
        print("Running native C++ Git miner to extract commit footprints...")

        result = subprocess.run(
            [self.miner_executable, str(self.repository)],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            try: 
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                print("Error parsing Git miner outputt. Ensure the C++ binary compiled correctly.")
                return []
        else:
            print("Git miner execution failed.")
            return[]

    def export_history(self, output_path: str = "commit_log.json") -> str:
        data = self.extract_history()
        with open(output_path, "w") as f:
            json.dump(data, f, indent=4)
        return output_path
