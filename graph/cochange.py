import pickle
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


class CoChangeIndex:
    """Which files changed together in git history (mined once, cached per HEAD)."""

    def __init__(self, commits: list[list[str]]):
        self.commits = commits
        self.by_file: dict[str, set[int]] = defaultdict(set)
        for i, files in enumerate(commits):
            for f in files:
                self.by_file[f].add(i)

    @classmethod
    def mine(cls, repo: Path, cache_dir: Path, since="2 years ago", max_files=40):
        git = ["git", "-C", str(repo)]
        head = subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache = cache_dir / f"{repo.name}_{head[:10]}_cochange.pkl"
        if cache.exists():
            return cls(pickle.loads(cache.read_bytes()))

        out = subprocess.run(
            git + ["log", f"--since={since}", "--no-merges", "--name-only",
                   "--pretty=format:@@%H"],
            capture_output=True, text=True, check=True).stdout

        commits, cur = [], None
        for line in out.splitlines():
            if line.startswith("@@"):
                if cur:
                    commits.append(cur)
                cur = []
            elif line.strip() and cur is not None:
                cur.append(line.strip())
        if cur:
            commits.append(cur)

        # Mega-commits (mass renames, license headers, reformatting) are noise.
        commits = [c for c in commits if len(c) <= max_files]
        cache.write_bytes(pickle.dumps(commits))
        return cls(commits)

    def n(self, f):            return len(self.by_file.get(f, ()))
    def together(self, a, b):  return len(self.by_file.get(a, set()) & self.by_file.get(b, set()))

    def partners(self, f) -> Counter:
        c = Counter()
        for i in self.by_file.get(f, ()):
            for g in self.commits[i]:
                if g != f:
                    c[g] += 1
        return c