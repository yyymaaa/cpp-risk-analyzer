import subprocess
import sys
import os
import shutil

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import paths
console = Console()
app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="[bold #ff70a6]RISK[/] — C++ change-impact analyzer")

LEVELS = ["never", "moderate", "high", "critical"]
GRADES = ["LOW", "MODERATE", "HIGH", "CRITICAL"]
BLOCK_EXIT = 3 

def _git_config(repo: Path, key: str):
    r = subprocess.run(["git", "-C", str(repo), "config", "--get", key], capture_output=True, text=True)
    return r.stdout.strip() or None


def _ask_commit_anyway():
    """True = y, False = n/Enter, None = no terminal available."""
    try:
        with open("/dev/tty", "w") as out:
            out.write("\nCommit anyway? [y/N] ")
            out.flush()
        with open("/dev/tty", "r") as inp:
            return inp.readline().strip().lower() in ("y", "yes")
    except OSError as e:
        console.print(f"\n[dim]No terminal to ask on ({e}). Commit allowed.[/]")
        return None


def _print_findings(reports):
    from graph.impact_report import GRADE_COLOR
    reports = sorted(reports, key=lambda r: GRADES.index(r.grade), reverse=True)
    for r in reports:
        c = GRADE_COLOR[r.grade]
        console.print(f"[{c}]■ {r.grade:<9}[/] {r.target}  "
                      f"[dim]{len(r.tier('REVIEW'))} to review of {r.reachable} reachable[/]")
    for r in reports[:2]:                                   # evidence for the two riskiest files
        rev = r.tier("REVIEW")[:3]
        if rev:
            console.print(f"\n[bold #c77dff]Most likely to break because of {r.target.split('/')[-1]}:[/]")
            for h in rev:
                console.print(f"  [bold white]{h.file}[/]  [#ff70a6]{h.score:.0f}[/]")
                for w in h.why[:2]:
                    console.print(f"     [#b28dff]· {w}[/]")
    tests = {}
    for r in reports:
        for h in r.hits:
            if h.tier == "RUN":
                tests[h.file] = max(tests.get(h.file, 0), h.score)
    if tests:
        console.print(f"\n[bold #c77dff]Run these {len(tests)} tests first:[/]")
        ranked = sorted(tests, key=tests.get, reverse=True)
        for t in ranked[:10]:
            console.print(f"  [#b28dff]▸[/] {t}")
        if len(ranked) > 10:
            console.print(f"  [dim]+ {len(ranked) - 10} more[/]")


def find_repo(repo: Optional[Path]) -> Path:
    if repo:
        return repo.resolve()
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if r.returncode:
        raise typer.BadParameter("Not inside a git repo. Pass --repo.")
    return Path(r.stdout.strip())


def has_model(repo: Path) -> bool:
    return (paths.models_dir() / f"{repo.name}_rf_regressor.joblib").exists()


def run(script: str, *args):
    subprocess.run([sys.executable, str(ROOT / script), *map(str, args)], check=True)


@app.command()
def build(repo: Optional[Path] = typer.Argument(None), verbose: bool = typer.Option(False, "-v")):
    """Extract metrics, build dataset, train model."""
    repo = find_repo(repo)
    run("core/main.py", repo, *(["-v"] if verbose else []))
    run("ml_pipeline/dataset_builder.py", repo)
    run("ml_pipeline/train_model.py", repo)
    console.print(f"[dim]Models and data for '{repo.name}' are stored in {paths.storage_root()} "
                  f"(set RISK_HOME to change this).[/]")


def _analyzer(repo: Path):
    sys.path.insert(0, str(ROOT))
    if not has_model(repo):
        # Never wait for an answer that can't come (scripts, CI, piped input): say what to do instead.
        if not sys.stdin.isatty():
            console.print(f"[bold #ff70a6]No model for '{repo.name}'.[/] Run `risk build {repo}` first "
                          f"(models are stored by folder name, so a renamed clone needs its own build).")
            raise typer.Exit(1)
        if typer.confirm(f"No model for '{repo.name}'. Build one now?", default=True):
            build(repo, False)
    from graph.impact_analyzer import ChangeImpactAnalyzer
    return ChangeImpactAnalyzer(repo)


def _rel(repo: Path, f: str) -> str:
    """Accept a path relative to the current folder, relative to the repo root, or absolute."""
    p = Path(f)
    candidates = [p] if p.is_absolute() else [Path.cwd() / p, repo / p]
    for c in candidates:
        c = c.resolve()
        if c.is_relative_to(repo) and c.exists():
            return c.relative_to(repo).as_posix()
    raise typer.BadParameter(f"'{f}' is not a file inside {repo}. Use a path relative to the repository "
                             f"root (e.g. include/leveldb/db.h) or to your current folder.")


@app.command()
def impact(file: str,
           repo: Optional[Path] = typer.Option(None, "--repo", "-r"),
           show_all: bool = typer.Option(False, "--all", "-a", help="Show watch-tier files, every test and every tool.")):
    """What breaks if I change FILE?"""
    repo = find_repo(repo)
    _analyzer(repo).analyze_impact(_rel(repo, file), show_all=show_all)


def _check(staged: bool, gate: bool, fail_on, repo: Path):
    from graph.impact_report import compute_report
    diff = ["git", "-C", str(repo), "diff", "--name-only"] + (["--cached"] if staged else ["HEAD"])
    files = [f for f in subprocess.run(diff, capture_output=True, text=True).stdout.split()
             if f.endswith((".h", ".hpp", ".cc", ".cpp", ".cxx", ".c"))]
    if not files:
        if not gate:
            console.print("[#b28dff]No C++ changes to analyze.[/]")
        return
    if gate and not has_model(repo):
        console.print("[dim]risk: no model yet, so no check this time. Run `risk init` once.[/]")
        return

    level = fail_on or ((_git_config(repo, "risk.level") or "high") if gate else "never")
    if level not in LEVELS:
        level = "high"

    an = _analyzer(repo)
    reports = [compute_report(an, f) for f in files if f in an.graph.nodes]
    if not reports:
        return
    worst = max(GRADES.index(r.grade) for r in reports)
    blocked = level != "never" and worst >= LEVELS.index(level)

    if gate and not blocked:
        console.print(f"[#b28dff]✔ risk check: {GRADES[worst]}. Go ahead.[/]")
        return

    _print_findings(reports)

    if gate:
        answer = _ask_commit_anyway()
        if answer is None:
            console.print("\n[dim]No terminal to ask on. Commit allowed.[/]")
            return
        if answer:
            console.print("[#b28dff]Okay, committing anyway.[/]")
            return
        console.print("\n[bold #ff70a6]Commit cancelled.[/] Run the tests above, then commit again.")
        raise typer.Exit(BLOCK_EXIT)
    if blocked:
        raise typer.Exit(1)


@app.command()
def check(staged: bool = typer.Option(True, help="Use staged changes (else working tree vs HEAD)"),
          gate: bool = typer.Option(False, "--gate", help="Hook mode: ask before a risky commit."),
          fail_on: Optional[str] = typer.Option(None, help="never | moderate | high | critical"),
          repo: Optional[Path] = typer.Option(None, "--repo", "-r")):
    """Analyze everything in your current diff."""
    if gate and os.environ.get("RISK_SKIP"):
        return
    try:
        _check(staged, gate, fail_on, find_repo(repo))
    except typer.Exit:
        raise
    except Exception as e:
        if not gate:
            raise
        console.print(f"[dim]risk: skipped ({type(e).__name__}: {e}). Commit not blocked.[/]")


HOOK_MARK = "# risk-analyzer hook"


@app.command("install-hooks")
def install_hooks(repo: Optional[Path] = typer.Option(None, "--repo", "-r")):
    """Check every commit automatically (asks before risky ones)."""
    repo = find_repo(repo)
    rel = subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-path", "hooks/pre-commit"],
                         capture_output=True, text=True, check=True).stdout.strip()
    hook = repo / rel
    hook.parent.mkdir(parents=True, exist_ok=True)
    if hook.exists() and HOOK_MARK not in hook.read_text():
        hook.rename(hook.with_name("pre-commit.backup"))
        console.print("[dim]Existing pre-commit hook saved as pre-commit.backup[/]")
    exe = shutil.which("risk")
    cmd = f'"{exe}"' if exe else f'"{sys.executable}" "{ROOT / "risk_cli.py"}"'
    hook.write_text(f'#!/bin/sh\n{HOOK_MARK}\n{cmd} check --gate\nrc=$?\n'
                    f'[ "$rc" -eq {BLOCK_EXIT} ] && exit 1\nexit 0\n')
    hook.chmod(0o755)
    console.print(f"[bold #ff70a6]Installed.[/] Commits in {repo.name} are now checked automatically.")


@app.command()
def init(repo: Optional[Path] = typer.Option(None, "--repo", "-r"),
         level: str = typer.Option("high", help="Ask before commits at this level or above: moderate | high | critical")):
    """One-time setup: train the model if needed, then turn on the commit guard."""
    if level not in LEVELS[1:]:
        raise typer.BadParameter("level must be moderate, high or critical")
    repo = find_repo(repo)
    if not has_model(repo):
        console.print(f"[bold #c77dff]No model for {repo.name} yet. Training one (a few minutes, once).[/]")
        build(repo, False)
    install_hooks(repo)
    subprocess.run(["git", "-C", str(repo), "config", "risk.level", level], check=True)
    console.print(f"[#b28dff]Will ask before any commit rated {level.upper()} or worse. "
                  f"Change it with `risk init --level critical`.[/]")

if __name__ == "__main__":
    app()
