# C++ Dependency Risk Analyzer

A machine learning-driven (regression), polyglot static analysis system designed to predict the change propagation risk ("blast radius") in large-scale C++ codebases.

Unlike traditional static analysis tools that merely describe structural complexity, this system is prescriptive. It bridges structural graph metrics (PageRank, Fan-in, Betweenness) with historical version-control telemetry (churn, temporal co-change events) to predict exactly how many downstream files will break when a specific file is modified.

# Key Features
1. Risk Prediction (ML Regression): Uses a Random Forest Regressor trained on chronological repository snapshots to predict the continuous transitive blast radius of a file, successfully avoiding temporal data leakage.
2. Structural Graph Analysis: Parses C++ #include relationships and constructs a directed dependency graph using NetworkX to compute architectural metrics.
3. Historical Telemetry Mining: Interrogates Git history to calculate temporal volatility, file churn, and historical co-change events.
4. Prescriptive Change-Impact Engine: Traces a proposed file modification backward through the dependency graph, ranks all transitive dependents by ML-predicted risk, and outputs a Prescriptive Maintenance Matrix.
5. Developer-Friendly CLI: A native bash wrapper (risk) that abstracts the Python virtual environment and execution pipeline into simple, standard commands.

# Tech Stack & Architecture
1. Orchestration & ML: Python 3, Scikit-Learn, Pandas, NumPy
2. Graph Mathematics: NetworkX
3. Native Parsing: C++17, GCC (via shell scripts) for native semantic AST parsing (libclang).
4. Data Layer: MySQL for relational normalization and complex temporal joins.
5. VCS Integration: Git CLI via Python Subprocess

# Prerequisites
To run this system, ensure your environment (tested on Fedora Linux) has the following installed:
1. Python 3.10+
2. GCC (GNU Compiler Collection) 13+
3. MySQL / MariaDB Server
4. Git

# Installation & Setup
1. Clone the repository
`print(git clone https://github.com/yyymaaa/cpp-risk-analyzer.git)`
`print(cd cpp-risk-analyzer)`
   
2. Set up the Python Virtual Environment
`python3 -m venv .venv`
`source .venv/bin/activate`
`pip install -r requirements.txt`

3. Configure the Database
Ensure your local MySQL/MariaDB server is running. Create a database named `cpp_risk_analyzer` and update the `db_config.json` with your local credentials.

4. Make the CLI executable
`chmod +x risk`

# Usage
The system is operated entirely through the `risk` CLI tool, which automatically handles environment activation.
1. Build & Train the Model
Extract structural dependencies, mine Git history, construct the chronologically split temporal dataset, and train the Random Forest Regressor.
`./risk build /path/to/target/cpp/repository`
2. Run Change-Impact Analysis
Evaluate the risk of modifying a specific file. The system will traverse the structural graph, identify all files affected by this change, rank them by ML-predicted risk, and output concrete CI/CD review actions.
`./risk impact include/leveldb/db.h`
Example output
<pre>
  ============================================================
CHANGE IMPACT REPORT: include/leveldb/db.h
============================================================
Direct & Transitive Dependents Found: 39

TOP RISK HOTSPOTS TO TEST/REVIEW:

1. db/snapshot.h
   Predicted Blast Radius: 13.66 files
   ACTION -> MANDATORY: Require 2 Senior Architect reviews. Trigger full nightly integration test suite.
   * High Structural Centrality: PageRank is in the top 10% of the codebase.

2. util/hash.cc
   Predicted Blast Radius: 6.01 files
   ACTION -> ELEVATED: Require 1 Senior review. Run targeted subsystem fuzzing and regression tests.
   * Historical Volatility: Highly active recently with 3 commits in the last year.
   * Ripple Effect: Historically triggers widespread co-changes when modified.
</pre>

# Repository Structure
<pre>
  cpp-risk-analyzer/
├── risk                        # Main CLI Executable Wrapper
├── src/
│   ├── main.py                 # Core orchestration pipeline
│   ├── scanner.py              # C++ repository file discovery
│   ├── parser.py               # Lexical C++ #include extraction
│   ├── graph_builder.py        # NetworkX directed graph construction
│   ├── analyzer.py             # Structural metric computation (PageRank, etc.)
│   ├── historical_graph.py     # Chronological graph state reconstruction
│   ├── dataset_builder.py      # Temporal feature engineering & blast-radius labeling
│   ├── train_model.py          # Random Forest Regressor training & evaluation
│   ├── impact_analyzer.py      # Explainability & change-impact traversal engine
│   ├── db_loader.py            # MySQL normalization and ingestion
│   ├── semantic_parser.cpp     # Native Clang AST parser (Feature branch)
│   └── compile.sh              # GCC compilation script
├── models/                     # Ignored directory for generated .joblib models
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
</pre>

# Methodology Note: Construct Validity
Initial iterations of this project evaluated risk as a binary classification task based on developer commit message keywords (e.g., `fix`, `bug`). Empirical testing on the `LevelD`B repository revealed extreme label noise and data sparsity with this heuristic. The architecture was successfully pivoted to a continuous regression target (downstream co-change blast radius), yielding a highly stable model capable of outperforming static structural heuristics (RMSE: 3.11 vs Baseline: 4.63).

# License
This project was developed as a final-year research project for the Bachelor of Science in Informatics and Computer Science at Strathmore University.
