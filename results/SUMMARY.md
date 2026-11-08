# Evaluation results

All runs use the frozen analyzer code, identical to the public release **v1.0.0** (git tag `v1.0.0`); the model and all baselines were fixed before any of these results were produced, and each repository was run once. Reproduce with `RISK_HOME=... risk build <repo>` at the commits listed.

**Reproducibility check (v1.1.0):** after the v1.1.0 packaging and cross-platform changes, LevelDB, Catch2 and Abseil were rebuilt with the final v1.1.0 code; every metric matched the frozen runs (identical, apart from floating-point rounding below 1e-12 caused by parallel tree training).

```
analyzer_code: identical to public release v1.0.0 (local freeze tag v1.0-eval)
python: Python 3.13.18
machine: 2 cores, 7 GB RAM, Linux 6.18.44-fc-v310
packages:
  joblib==1.6.0
  networkx==3.7
  numpy==2.5.4
  pandas==3.1.1
  scikit-learn==1.9.1
  scipy==1.18.1
```

## Repositories

| Repository | Commit | Commit date | Total commits | Snapshots | Test period | Test rows with activity | Build time |
|---|---|---|---|---|---|---|---|
| leveldb | `bb74ef7399` | 2026-09-01 | 449 | 59 | 2023-10-16 → 2026-07-02 | 5 of 1584 (0.3%) | 0 min 33 s |
| Catch2 | `a1a991fee5` | 2026-10-09 | 4834 | 33 | 2024-11-15 → 2026-05-09 | 257 of 2680 (9.6%) | 0 min 30 s |
| abseil-cpp | `28d518b05d` | 2026-11-07 | 3990 | 33 | 2025-02-14 → 2026-08-08 | 1252 of 5927 (21.1%) | 1 min 26 s |
| rocksdb | `553b52b4a7` | 2026-10-21 | 14213 | 59 | 2023-10-16 → 2026-07-02 | 3186 of 15497 (20.6%) | 4 min 2 s |
| bitcoin | `4ef7904c39` | 2026-11-08 | 51516 | 59 | 2023-11-21 → 2026-08-07 | 3949 of 14135 (27.9%) | 4 min 40 s |

## Does the Random Forest beat the strongest baseline?

| Repository | Evaluation | RF RMSE | Best baseline (RMSE) | RF Spearman | Best baseline Spearman | RF beats best baseline on |
|---|---|---|---|---|---|---|
| leveldb | held-out ⚠ | 0.86 | train median (0.22) | 0.124 | 0.035 | Spearman, NDCG@10% |
| leveldb | rolling | 9.64 | train mean (8.26) | 0.063 | 0.101 | none |
| Catch2 | held-out | 3.41 | train median (2.68) | 0.164 | 0.138 | Spearman |
| Catch2 | rolling | 9.44 | train median (7.73) | 0.130 | 0.117 | Spearman |
| abseil-cpp | held-out | 8.76 | weighted heuristic (8.75) | 0.222 | 0.216 | Spearman, NDCG@10% |
| abseil-cpp | rolling | 7.19 | weighted heuristic (7.17) | 0.245 | 0.219 | Spearman, NDCG@10% |
| rocksdb | held-out | 12.40 | past co-change count (12.75) | 0.463 | 0.423 | RMSE, R², Spearman, NDCG@10% |
| rocksdb | rolling | 13.68 | past co-change count (14.06) | 0.465 | 0.422 | RMSE, R², Spearman, NDCG@10% |
| bitcoin | held-out | 10.61 | past co-change count (11.04) | 0.454 | 0.379 | RMSE, R², Spearman, NDCG@10% |
| bitcoin | rolling | 10.71 | past co-change count (10.99) | 0.517 | 0.474 | RMSE, R², Spearman, NDCG@10% |

## leveldb

### Held-out test period (2023-10-16 → 2026-07-02)
> ⚠ Low-activity test period: held-out metrics are unreliable for this repository.

| Predictor | RMSE | MAE | R² | Spearman | NDCG@10% |
|---|---|---|---|---|---|
| Random Forest | 0.864 | 0.432 | -13.820 | **0.124** | **0.384** |
| weighted heuristic | 2.427 | 2.345 | -115.996 | 0.035 | 0.339 |
| past co-change count | 0.293 | 0.044 | -0.705 | -0.012 | 0.000 |
| previous label | 0.318 | 0.025 | -1.006 | -0.012 | 0.000 |
| train mean | 2.329 | 2.329 | -106.723 | -0.012 | 0.000 |
| train median | **0.225** | **0.013** | **-0.003** | -0.012 | 0.000 |

### Rolling-origin evaluation (51 test snapshots)
| Predictor | RMSE | MAE | R² | Spearman | NDCG@10% |
|---|---|---|---|---|---|
| Random Forest | 9.639 | 3.635 | -0.382 | 0.063 | 0.222 |
| weighted heuristic | 8.294 | 3.688 | -0.023 | 0.055 | 0.167 |
| past co-change count | 8.873 | 3.378 | -0.171 | **0.101** | **0.271** |
| previous label | 11.517 | 3.458 | -0.973 | 0.053 | 0.209 |
| train mean | **8.263** | 3.673 | **-0.016** | 0.021 | 0.130 |
| train median | 8.398 | **1.817** | -0.049 | 0.021 | 0.130 |

Error analysis: [`leveldb/error_analysis.md`](leveldb/error_analysis.md)

## Catch2

### Held-out test period (2024-11-15 → 2026-05-09)
| Predictor | RMSE | MAE | R² | Spearman | NDCG@10% |
|---|---|---|---|---|---|
| Random Forest | 3.412 | 1.750 | -0.719 | **0.164** | 0.178 |
| weighted heuristic | 3.646 | 3.145 | -0.962 | 0.138 | 0.175 |
| past co-change count | 3.093 | 1.204 | -0.412 | 0.121 | 0.194 |
| previous label | 3.808 | 1.162 | -1.141 | 0.111 | **0.329** |
| train mean | 3.560 | 3.177 | -0.871 | -0.004 | 0.074 |
| train median | **2.676** | **0.622** | **-0.057** | -0.004 | 0.074 |

### Rolling-origin evaluation (25 test snapshots)
| Predictor | RMSE | MAE | R² | Spearman | NDCG@10% |
|---|---|---|---|---|---|
| Random Forest | 9.437 | 4.627 | -0.584 | **0.130** | 0.212 |
| weighted heuristic | 7.944 | 5.181 | -0.122 | 0.115 | 0.215 |
| past co-change count | 8.966 | 4.094 | -0.429 | 0.117 | 0.234 |
| previous label | 10.359 | 3.675 | -0.908 | 0.087 | **0.250** |
| train mean | 7.777 | 5.212 | -0.075 | -0.011 | 0.100 |
| train median | **7.726** | **2.097** | **-0.061** | -0.011 | 0.100 |

Error analysis: [`Catch2/error_analysis.md`](Catch2/error_analysis.md)

## abseil-cpp

### Held-out test period (2025-02-14 → 2026-08-08)
| Predictor | RMSE | MAE | R² | Spearman | NDCG@10% |
|---|---|---|---|---|---|
| Random Forest | 8.762 | 3.846 | 0.008 | **0.222** | **0.310** |
| weighted heuristic | **8.752** | 4.657 | **0.010** | 0.182 | 0.246 |
| past co-change count | 9.117 | 3.815 | -0.074 | 0.216 | 0.190 |
| previous label | 11.314 | 4.417 | -0.654 | 0.151 | 0.204 |
| train mean | 8.802 | 4.748 | -0.001 | 0.001 | 0.116 |
| train median | 9.306 | **3.037** | -0.119 | 0.001 | 0.116 |

### Rolling-origin evaluation (25 test snapshots)
| Predictor | RMSE | MAE | R² | Spearman | NDCG@10% |
|---|---|---|---|---|---|
| Random Forest | 7.187 | 3.590 | -0.067 | **0.245** | **0.342** |
| weighted heuristic | **7.171** | 4.547 | **-0.062** | 0.193 | 0.278 |
| past co-change count | 7.330 | 3.186 | -0.110 | 0.219 | 0.284 |
| previous label | 9.022 | 3.308 | -0.682 | 0.149 | 0.276 |
| train mean | 7.206 | 4.667 | -0.073 | 0.003 | 0.091 |
| train median | 7.275 | **2.127** | -0.093 | 0.003 | 0.091 |

Error analysis: [`abseil-cpp/error_analysis.md`](abseil-cpp/error_analysis.md)

## rocksdb

### Held-out test period (2023-10-16 → 2026-07-02)
| Predictor | RMSE | MAE | R² | Spearman | NDCG@10% |
|---|---|---|---|---|---|
| Random Forest | **12.398** | 6.765 | **0.336** | **0.463** | **0.647** |
| weighted heuristic | 14.982 | 9.981 | 0.030 | 0.328 | 0.336 |
| past co-change count | 12.747 | 5.881 | 0.298 | 0.423 | 0.635 |
| previous label | 14.799 | 6.105 | 0.053 | 0.300 | 0.562 |
| train mean | 15.447 | 10.503 | -0.031 | -0.018 | 0.098 |
| train median | 16.127 | **5.360** | -0.124 | -0.018 | 0.098 |

### Rolling-origin evaluation (51 test snapshots)
| Predictor | RMSE | MAE | R² | Spearman | NDCG@10% |
|---|---|---|---|---|---|
| Random Forest | **13.678** | 7.994 | **0.293** | **0.465** | **0.654** |
| weighted heuristic | 15.786 | 10.449 | 0.058 | 0.325 | 0.360 |
| past co-change count | 14.060 | 7.823 | 0.253 | 0.422 | 0.644 |
| previous label | 16.744 | 8.093 | -0.059 | 0.328 | 0.559 |
| train mean | 16.292 | 11.034 | -0.003 | -0.003 | 0.144 |
| train median | 17.673 | **7.041** | -0.180 | -0.003 | 0.144 |

Error analysis: [`rocksdb/error_analysis.md`](rocksdb/error_analysis.md)

## bitcoin

### Held-out test period (2023-11-21 → 2026-08-07)
| Predictor | RMSE | MAE | R² | Spearman | NDCG@10% |
|---|---|---|---|---|---|
| Random Forest | **10.608** | 6.110 | **0.171** | **0.454** | **0.550** |
| weighted heuristic | 11.387 | 7.239 | 0.045 | 0.319 | 0.230 |
| past co-change count | 11.042 | 5.896 | 0.102 | 0.379 | 0.525 |
| previous label | 13.961 | 6.522 | -0.435 | 0.263 | 0.418 |
| train mean | 11.668 | 7.562 | -0.003 | -0.002 | 0.117 |
| train median | 12.589 | **4.764** | -0.167 | -0.002 | 0.117 |

### Rolling-origin evaluation (51 test snapshots)
| Predictor | RMSE | MAE | R² | Spearman | NDCG@10% |
|---|---|---|---|---|---|
| Random Forest | **10.707** | 6.123 | **0.198** | **0.517** | **0.605** |
| weighted heuristic | 11.641 | 7.352 | 0.052 | 0.388 | 0.256 |
| past co-change count | 10.988 | 5.939 | 0.155 | 0.474 | 0.584 |
| previous label | 13.690 | 6.505 | -0.311 | 0.349 | 0.486 |
| train mean | 11.968 | 7.756 | -0.002 | 0.004 | 0.144 |
| train median | 13.007 | **5.124** | -0.184 | 0.004 | 0.144 |

Error analysis: [`bitcoin/error_analysis.md`](bitcoin/error_analysis.md)

