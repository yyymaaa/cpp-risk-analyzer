"""Main entry point for extracting C++ codebase structural metrics and ingesting to MySQL."""
import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.scanner import scan_repository
from core.parser import extract_includes
from graph.graph_builder import build_dependency_graph
from graph.validator import GraphValidator
from graph.analyzer import StructuralAnalyzer
from git_mining.git_analyzer import GitAnalyzer
from database.db_loader import DatabaseLoader

# Define Custom Pink & Purple Theme
custom_theme = Theme({
    "info": "#b28dff",          # Light pastel purple
    "success": "bold #ff70a6",  # Vibrant pink
    "warning": "#ffb8d1",       # Light pink
    "error": "bold #ff0a54",    # Deep red-pink
    "highlight": "bold #c77dff" # Vibrant purple
})

console = Console(theme=custom_theme)

def print_banner():
    """Renders a styled CLI banner."""
    banner_text = Text("C++ RISK ANALYZER", style="bold #ff70a6", justify="center")
    banner_text.append("\nStructural Extraction & Ingestion Pipeline", style="#c77dff")
    console.print(Panel(banner_text, border_style="#b28dff", padding=(1, 2)))

def main():
    parser = argparse.ArgumentParser(
        description="Extract C++ structural metrics and ingest into MySQL."
    )
    parser.add_argument("repository", type=Path, help="Path to target C++ repository")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed node counts and graph validation reports")
    args = parser.parse_args()

    repository = args.repository.resolve()
    
    if not repository.is_dir():
        console.print(f"[error]Error: '{repository}' is not a valid directory.[/error]")
        sys.exit(1)

    repo_name = repository.name
    print_banner()

    # Step 1: Scanning
    with console.status("[info]Scanning repository for C++ files...", spinner="pong"):
        files = scan_repository(repository)
        
    if not files:
        console.print(f"[error]Error: No C++ source/header files found in '{repository}'. Aborting pipeline.[/error]")
        sys.exit(1)
        
    console.print(f"[success]✔ Found {len(files)} C++ source files.[/success]")

    # Step 2: Graph Building & Validation
    with console.status("[info]Building structural dependency graph...", spinner="pong"):
        dependencies = {f: extract_includes(f) for f in files}
        graph = build_dependency_graph(repository, files, dependencies)
        
        validator = GraphValidator(graph)
        report = validator.generate_report()

    # Only show raw graph metrics if the user passes the -v flag
    if args.verbose:
        console.print(f"[highlight]Graph contains {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.[/highlight]")
        console.print(f"[info]{report}[/info]")

    console.print("[success]✔ Dependency graph built and validated.[/success]")

    # Step 3: Structural Analysis
    metrics_output = PROJECT_ROOT / "data" / "extraction_output" / f"{repo_name}_structural_metrics.json"
    with console.status("[info]Calculating structural metrics (PageRank, Fan-in/out)...", spinner="pong"):
        analyzer = StructuralAnalyzer(graph)
        metrics_output.parent.mkdir(parents=True, exist_ok=True)
        analyzer.export_metrics(output_path=metrics_output)
        
    console.print(f"[success]✔ Structural metrics exported.[/success]")

    # Step 4: Git Mining
    git_output = PROJECT_ROOT / "data" / "extraction_output" / f"{repo_name}_commit_log.json"
    with console.status("[info]Mining historical Git commit logs...", spinner="pong"):
        git_analyzer = GitAnalyzer(repository)
        git_analyzer.export_history(output_path=git_output)
        
    console.print(f"[success]✔ Raw Git commit log exported.[/success]")

    # Step 5: MySQL Ingestion
    with console.status("[info]Ingesting artifacts into MySQL database...", spinner="pong"):
        db_loader = DatabaseLoader()
        db_loader.load_structural_data(metrics_output, repo_name=repo_name)
        db_loader.load_git_data(git_output, repo_name=repo_name)
        db_loader.close()
        
    console.print("[success]✔ JSON artifacts normalized and ingested into MySQL.[/success]\n")
    
if __name__ == "__main__":
    main()