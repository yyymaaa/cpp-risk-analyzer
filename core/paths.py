"""Single source of truth for where the analyzer stores its files.

Resolution order for the storage root:
  1. $RISK_HOME, if set (useful for Docker, CI and tests).
  2. The project folder, when running from a source checkout (a folder containing
     pyproject.toml, e.g. after `git clone` + `pip install -e .`). This keeps the
     developer workflow and the committed evaluation data exactly where they were.
  3. Otherwise (a normal `pip install` / `pipx install`): the per-user data folder,
     $XDG_DATA_HOME/cpp-risk-analyzer or ~/.local/share/cpp-risk-analyzer.

Inside the root:  data/extraction_output, data/ml_datasets, data/cache,
                  data/configuration/db_config.json, models/
"""
import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def storage_root() -> Path:
    env = os.environ.get("RISK_HOME")
    if env:
        return Path(env).expanduser().resolve()
    if (PACKAGE_ROOT / "pyproject.toml").exists():
        return PACKAGE_ROOT
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base).expanduser() / "cpp-risk-analyzer"


def _dir(*parts: str) -> Path:
    d = storage_root().joinpath(*parts)
    d.mkdir(parents=True, exist_ok=True)
    return d


def extraction_dir() -> Path:
    return _dir("data", "extraction_output")


def datasets_dir() -> Path:
    return _dir("data", "ml_datasets")


def cache_dir() -> Path:
    return _dir("data", "cache")


def models_dir() -> Path:
    return _dir("models")


def db_config_path() -> Path:
    return _dir("data", "configuration") / "db_config.json"
