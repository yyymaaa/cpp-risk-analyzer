"""Shared fixtures: small, fully controlled C++ repositories with real Git history.

Test docstrings follow a fixed format that tests/make_test_record.py turns into the test record:
    <what is tested>
    Req: <requirement id(s) from Chapter 4>
    Expected: <expected result>
"""
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def git(repo: Path, *args, date: str | None = None):
    env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com",
           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com"}
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True, env=env).stdout


def write(repo: Path, rel: str, text: str):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def commit(repo: Path, message: str, date: datetime):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", message, date=date.strftime("%Y-%m-%dT%H:%M:%S"))


# A small library with a clear dependency structure:
#   core.h  <- util.h <- engine.cc        (engine.cc depends on util.h, which depends on core.h)
#   core.h  <- api.h  <- api.cc
#   core.h  <- tests/core_test.cc
#   tools/cli.cc -> api.h
FILES = {
    "include/lib/core.h": '#pragma once\nint core();\n',
    "include/lib/util.h": '#pragma once\n#include "lib/core.h"\nint util();\n',
    "include/lib/api.h": '#pragma once\n#include "lib/core.h"\n#include <string>\nint api();\n',
    "src/engine.cc": '#include "lib/util.h"\n#include <vector>\nint engine() { return util(); }\n',
    "src/api.cc": '#include "lib/api.h"\nint api() { return core(); }\n',
    "tests/core_test.cc": '#include "lib/core.h"\nint main() { return core(); }\n',
    "tools/cli.cc": '#include "lib/api.h"\nint main() { return api(); }\n',
}


@pytest.fixture
def tiny_repo(tmp_path) -> Path:
    """A 7-file C++ repository with a single initial commit."""
    repo = tmp_path / "tinylib"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    for rel, text in FILES.items():
        write(repo, rel, text)
    commit(repo, "initial", datetime(2020, 1, 1))
    return repo


def make_history_repo(root: Path, name="histlib", years=4, step_days=10) -> Path:
    """The tiny library with `years` of deterministic history.

    core.h and util.h usually change together with engine.cc (a strong co-change pattern),
    api.h changes with api.cc, and every 7th commit is a bug fix.
    """
    repo = root / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    for rel, text in FILES.items():
        write(repo, rel, text)
    start = datetime(2019, 1, 1)
    commit(repo, "initial", start)
    groups = [["include/lib/core.h", "include/lib/util.h", "src/engine.cc"],
              ["include/lib/api.h", "src/api.cc"],
              ["include/lib/core.h", "tests/core_test.cc"],
              ["src/engine.cc"]]
    n = years * 365 // step_days
    for i in range(1, n):
        for rel in groups[i % len(groups)]:
            with (repo / rel).open("a") as f:
                f.write(f"// change {i}\n")
        msg = f"fix bug {i}" if i % 7 == 0 else f"feature {i}"
        commit(repo, msg, start + timedelta(days=i * step_days))
    return repo


@pytest.fixture
def history_repo(tmp_path) -> Path:
    return make_history_repo(tmp_path)


@pytest.fixture
def risk_home(tmp_path, monkeypatch) -> Path:
    """Isolated storage root so tests never touch real models or data."""
    home = tmp_path / "risk_home"
    monkeypatch.setenv("RISK_HOME", str(home))
    return home
