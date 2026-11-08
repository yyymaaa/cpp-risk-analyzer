# C++ Dependency Risk Analyzer

A machine-learning-assisted static analysis tool that estimates the **change propagation risk ("blast radius")** of files in large C++ codebases, and tells a developer which files to review and which tests to run before committing a change.

It combines **structural graph metrics** from `#include` relationships (PageRank, fan-in/out, betweenness) with **Git history** (churn, bug-fix commits, co-change events) and trains a Random Forest regressor to predict how many other files are likely to change together with a given file in the next 90 days.

## Key Features
1. **Blast-radius prediction (ML regression):** a Random Forest trained on chronological repository snapshots, with a time-ordered train/test split and purging of overlapping label windows to prevent temporal data leakage.
2. **Structural graph analysis:** parses C++ `#include` directives and builds a directed dependency graph (NetworkX).
3. **Historical telemetry mining:** commit frequency, corrective (bug-fix) commits, co-change partners and recency, mined from Git.
4. **Change-impact report:** traces a file's dependents through the include graph, ranks them by a risk score that combines include distance, Git co-change history and predicted blast radius, and lists files to review and tests to run.
5. **Commit guard:** an optional Git pre-commit hook that rates every commit and asks before committing a high-risk change; a `--fail-on` mode for CI.
6. **Honest evaluation:** every training run compares the model with four simple baselines on regression and ranking metrics, on a held-out period and with rolling-origin evaluation, and warns when the test period is too quiet to trust.

## How It Works
```
target C++ repo ──► scan files ──► parse #includes ──► dependency graph ──► structural metrics (JSON)
                └─► Git history ──► temporal snapshots (every 90 days) ──► training dataset (CSV)
                                                                              │
                         Random Forest + baselines ◄──────────────────────────┘
                                   │
          risk impact / risk check ◄── model + current graph + Git co-change
```
For each snapshot date, features describe the file **as of that date** (graph metrics on the code at that commit, Git activity in the previous 365 days). The label is the number of distinct files that changed together with it in the **following** 90 days.

## Prerequisites
Tested on Fedora Linux and Ubuntu 24.04.
- Python 3.10+
- Git
- *Optional:* MySQL / MariaDB (see [Database](#database-optional))
- *Optional:* GCC 13+ with `libgit2-devel` (only for the C++ Git miner used by the MySQL step)

## Installation

### For users: install the tool and run it on your own codebase
```bash
pipx install "git+https://github.com/yyymaaa/cpp-risk-analyzer@v1.0.0"
# or, inside a virtual environment:
pip install "git+https://github.com/yyymaaa/cpp-risk-analyzer@v1.0.0"
```
Then, from inside the C++ repository you are working on:
```bash
cd ~/code/my-cpp-project
risk build .                     # once: learn this repository's history (a few minutes)
risk impact src/engine/core.h    # before changing a file
risk init                        # optional: check every commit automatically
```
`pipx` is recommended: it installs the tool in its own isolated environment, so its dependencies never conflict with your other Python packages.

**Where files are stored.** Models, datasets and caches go to `~/.local/share/cpp-risk-analyzer/` (or `$XDG_DATA_HOME/cpp-risk-analyzer`). Nothing is written into your repository except the optional pre-commit hook. Set `RISK_HOME=/some/folder` to store them elsewhere. When running from a source checkout (below), the project folder itself is used.

### For development: from source
```bash
git clone https://github.com/yyymaaa/cpp-risk-analyzer.git
cd cpp-risk-analyzer
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"         # installs the `risk` command and pytest
```
Check it worked: `risk --help`

**Important:** the target repository must have its **full Git history**. A shallow clone (`git clone --depth ...`) gives too few snapshots; the tool warns when it detects one. To fix: `git -C /path/to/repo fetch --unshallow`.

## Usage
Run commands from anywhere; inside a Git repository the `--repo` option can be omitted.

### 1. Build and train (once per repository)
```bash
risk build /path/to/cpp-repo
```
Extracts the structural metrics, mines Git history, builds the temporal dataset, trains the model and prints the evaluation tables. On RocksDB (14,000+ commits) this takes about 4 minutes on a 2-core machine. Models are stored **by folder name**, so a clone with a different folder name needs its own build.

To train without the slower rolling evaluation: `python ml_pipeline/train_model.py /path/to/cpp-repo --no-rolling`

### 2. Analyze the impact of changing one file
```bash
risk impact include/leveldb/db.h --repo /path/to/leveldb
risk impact include/leveldb/db.h --repo /path/to/leveldb --all   # also show lower-priority files
```
Example output (abridged):
```
include/leveldb/db.h
████████████████░░░░  MODERATE   predicted to change alongside more files than 82% of the repo
39 files can reach this change.  Only 5 need your eyes.

REVIEW THESE  product code, ranked by risk score (include distance, git co-change, predicted blast radius)
  1. db/db_impl.h   49   └─ includes it directly
  2. db/dbformat.h  45   ├─ includes it directly
                         └─ 20 files depend on it in turn (top 10%)
RUN THESE TESTS  5 of 15 reachable tests are worth running
  ▸ db/recovery_test.cc
  ▸ db/db_test.cc
```
Every report shows the model's measured accuracy ("model trust") so the user can judge how much to rely on it. The risk score ranks files; it is **not** a calibrated probability.

### 3. Check your current changes
```bash
risk check                       # staged changes
risk check --no-staged           # working tree vs HEAD
risk check --fail-on high        # exit code 1 if any change is rated HIGH or above (for CI)
```

### 4. Turn on the commit guard
```bash
cd /path/to/cpp-repo
risk init                        # trains a model if needed, installs the pre-commit hook
risk init --level critical       # only ask before CRITICAL commits
```
The hook asks *"Commit anyway? [y/N]"* before risky commits. It never blocks a commit when it cannot run (no model, no terminal, or an internal error). Skip it once with `RISK_SKIP=1 git commit ...`.

### Legacy wrapper
`./risk build <repo>` and `./risk impact <file> <repo>` still work without installing; they use `.venv` automatically if present.

### Docker
```bash
docker build -t cpp-risk-analyzer .
docker run --rm \
  -v /path/to/rocksdb:/repos/rocksdb \
  -v "$PWD/models:/app/models" -v "$PWD/data:/app/data" \
  cpp-risk-analyzer build /repos/rocksdb
```
Mount the target repository under **its real folder name** (models are stored by folder name), and mount `models/` and `data/` so results survive after the container exits.

## Testing
```bash
python -m pytest                 # all 42 tests (about 30 seconds)
python -m pytest -m "not slow"   # unit tests only (a few seconds)
```
The suite covers include parsing, path resolution, graph construction and metrics, co-change mining, leakage prevention (purging and baselines), evaluation metrics, impact-report tiers, storage paths, CLI path handling, and end-to-end runs of `build`, `impact` and `check` on a generated repository with four years of Git history. GitHub Actions runs it on every push and pull request (Python 3.10 and 3.12), and also checks that a normal `pip install` works outside the project folder. The full test record (test, requirement, expected result, actual result, corrective action) is in [`tests/TEST_RECORD.md`](tests/TEST_RECORD.md).

## Releases
Pushing a version tag publishes a GitHub Release with an installable wheel (see `.github/workflows/release.yml`):
```bash
git tag v1.0.0 && git push origin v1.0.0
```

## Database (optional)
`risk build` can also normalize the extracted metrics and commit log into MySQL/MariaDB for SQL analysis. **The ML pipeline and impact analysis do not need it**; if no database is reachable the step is skipped with a warning.

To enable it:
1. Start MySQL/MariaDB and create the database: `CREATE DATABASE cpp_risk_analyzer;`
2. Copy `data/configuration/db_config.example.json` to `data/configuration/db_config.json` and set the `root` password. This file is gitignored; never commit it.
3. Optional: compile the C++ Git miner, which produces the commit log loaded into MySQL: `bash git_mining/compile_miner.sh`

## Data Sources and Ethics
The tool analyses **public open-source Git repositories** (evaluation used [google/leveldb](https://github.com/google/leveldb), [facebook/rocksdb](https://github.com/facebook/rocksdb), [abseil/abseil-cpp](https://github.com/abseil/abseil-cpp) and [catchorg/Catch2](https://github.com/catchorg/Catch2); licences: BSD-3-Clause, GPLv2 or Apache 2.0, Apache 2.0 and Boost 1.0 respectively). It reads only source code and commit metadata (file paths, timestamps, commit messages). No personal data is analysed; author names and emails are not used as features. Repositories are cloned locally and are not redistributed.

Preparation steps (all automated by `risk build`):
1. Scan C/C++ source and header files, excluding build output.
2. Resolve `#include` directives to files inside the repository (system and external headers are ignored).
3. Every 90 days of history, reconstruct the dependency graph at that commit and compute metrics.
4. Count Git activity in the previous 365 days (features) and co-changes in the next 90 days (label). Commits touching more than 50 files (bulk reformatting, renames) are excluded as noise.
5. Split chronologically: the latest 20% of snapshot dates form the test set.

Outputs: `data/extraction_output/` (metrics, commit log), `data/ml_datasets/` (training CSV), `models/` (model, feature importance, evaluation metrics JSON).

## Evaluation
**Validation approach.** Snapshots are split by time: the model is trained on earlier snapshots and tested on later ones, never the reverse. Training rows whose 90-day label window overlaps the test period are purged. The model is also evaluated with **rolling-origin evaluation**: for every snapshot T, it is retrained on all earlier snapshots and tested on T, so every period of the project's history is tested, not only the most recent 20%.

**Baselines.** The Random Forest is compared with five non-ML predictors: a **manually weighted heuristic** (equal weights on percentile-ranked fan-in, PageRank, commit count and past co-change count, fixed before evaluation), the training mean, the training median, the file's previous label, and its past-year co-change count.

**Metrics.** RMSE, MAE and R² measure how close the predicted blast radius is. Spearman correlation and NDCG@10% (computed within each snapshot) measure how well the model ranks files, which is how `risk impact` uses it.

**Protocol.** The analyzer code was frozen (git tag `v1.0-eval`) before the final runs, and each repository was evaluated once at a pinned commit. Full results, environment, logs and error analyses are in [`results/SUMMARY.md`](results/SUMMARY.md).

**Results: Random Forest vs the weighted heuristic**

| Repository | Commits | Test rows with activity | Held-out RMSE (RF / heuristic) | Rolling RMSE (RF / heuristic) | Held-out Spearman (RF / heuristic) | Rolling Spearman (RF / heuristic) |
|---|---|---|---|---|---|---|
| RocksDB | 14,213 | 20.6% | **12.40** / 14.98 | **13.68** / 15.79 | **0.463** / 0.328 | **0.465** / 0.325 |
| Abseil | 3,990 | 21.1% | 8.76 / 8.75 | 7.19 / 7.17 | **0.222** / 0.182 | **0.245** / 0.193 |
| Catch2 | 4,834 | 9.6% | **3.41** / 3.65 | 9.44 / **7.94** | **0.164** / 0.138 | **0.130** / 0.115 |
| LevelDB ⚠ | 449 | 0.3% | **0.86** / 2.43 | 9.64 / **8.29** | **0.124** / 0.035 | **0.063** / 0.055 |

⚠ LevelDB's held-out period has almost no development activity, so its held-out numbers are not meaningful.

**Interpretation.**
- **Ranking (what the tool uses):** the Random Forest ranks files better than the weighted heuristic on all four repositories in both evaluations, and better than every baseline in 7 of 8 evaluations.
- **Magnitude (RMSE):** the model is clearly more accurate only on RocksDB, the largest and most active repository (13–17% lower RMSE than the heuristic, R² 0.29–0.34). It ties the heuristic on Abseil. On the quieter Catch2 and LevelDB histories, simply predicting the training median gives a lower RMSE, because most files have a blast radius of 0.
- **Error analysis:** the model over-predicts files that end up not changing, and under-predicts the largest blast radii (on RocksDB, by about 24 files on average when the true value exceeds 20). It is therefore better used to *rank* files for review than to *estimate exact counts*. Historical co-change and commit activity are the most important features on RocksDB; structural features (PageRank, fan-out) matter more on Catch2.
- **Implication:** the approach adds value on large, actively developed repositories. On small or quiet ones it should be treated as a ranking hint, which the report states through its "model trust" line.

## Repository Structure
```
cpp-risk-analyzer/
├── risk_cli.py                 # Main CLI (`risk`): build, impact, check, init, install-hooks
├── risk                        # Legacy bash wrapper (build, impact)
├── core/
│   ├── main.py                 # Extraction pipeline: scan → graph → metrics → Git → MySQL (optional)
│   ├── scanner.py              # C/C++ file discovery
│   ├── parser.py               # #include extraction
│   ├── resolver.py             # Resolves includes to repository files
│   └── paths.py                # Where models, datasets and caches are stored
├── graph/
│   ├── graph_builder.py        # NetworkX dependency graph
│   ├── analyzer.py             # PageRank, fan-in/out, betweenness
│   ├── validator.py            # Graph sanity checks
│   ├── historical_graph.py     # Rebuilds the graph at a past commit
│   ├── cochange.py             # Git co-change index (cached per HEAD)
│   ├── impact_analyzer.py      # Loads model + graph, runs impact analysis
│   └── impact_report.py        # Risk scoring, tiers and terminal report
├── ml_pipeline/
│   ├── dataset_builder.py      # Temporal snapshots, features and labels
│   └── train_model.py          # Training, baselines, held-out and rolling evaluation
├── git_mining/                 # Git history export (Python + optional C++/libgit2 miner)
├── database/db_loader.py       # Optional MySQL ingestion
├── semantic/                   # Experimental Clang AST parser (not used by the main pipeline)
├── tests/                      # pytest suite, test record and its generator
├── results/                    # Frozen evaluation results, error analysis, environment
├── .github/workflows/          # CI (tests on every push) and release workflow
├── data/                       # Extraction outputs, datasets, cache, DB config example
├── models/                     # Trained models and metrics (gitignored)
├── dockerfile
├── requirements.txt
└── pyproject.toml
```

## Methodology Note: Construct Validity
Early iterations framed risk as binary classification, labelling a file "risky" when commit messages contained keywords such as `fix` or `bug`. Testing on LevelDB showed heavy label noise and sparsity with this heuristic, so the target was changed to a continuous regression label: the number of files that co-change with a file in the following 90 days (its downstream blast radius).

## Known Limitations
- **Needs active history:** the model is only informative on repositories with substantial, ongoing development (see LevelDB above).
- **Include-level dependencies only:** the graph captures `#include` relationships, not calls, templates or macros. The Clang-based semantic parser in `semantic/` is experimental.
- **Co-change is a proxy:** files changing together does not prove one change broke the other.
- **Heuristic risk score:** the review ranking combines include-distance weights that are set by hand, not learned or calibrated.
- **Only files that exist today are modelled:** the dataset follows files present at the analysed commit, so history of deleted or renamed files is lost (survivorship bias). Repositories that were reorganised (e.g. Catch2 around 2020) have few early snapshots.
- **Models are keyed by folder name:** two repositories with the same folder name overwrite each other's model.

## License
Developed as a final-year research project for the Bachelor of Science in Informatics and Computer Science at Strathmore University.
