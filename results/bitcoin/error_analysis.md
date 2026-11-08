# Error analysis: bitcoin (held-out test period)

Test rows: 14135 · rows with any co-change: 27.9%

## By file kind
| kind   |   rows |   mean_actual |   mean_predicted |   mae |   bias |
|:-------|-------:|--------------:|-----------------:|------:|-------:|
| prod   |   9281 |          4.64 |             5.38 |  5.6  |   0.74 |
| test   |   4161 |          4.83 |             6.32 |  6.79 |   1.49 |
| tool   |    693 |          5.98 |             5.87 |  8.89 |  -0.12 |

## By size of the actual blast radius
| bucket   |   rows |   mean_actual |   mean_predicted |   mae |   bias |
|:---------|-------:|--------------:|-----------------:|------:|-------:|
| 0        |  10186 |          0    |             3.65 |  3.65 |   3.65 |
| 1-5      |   1215 |          2.84 |             8.3  |  6.32 |   5.46 |
| 6-20     |   1484 |         11.67 |             9.96 |  7.17 |  -1.71 |
| >20      |   1250 |         37.25 |            14.65 | 24.73 | -22.6  |

*bias = mean(predicted − actual): negative means the model under-predicts.*

Summary: for files whose real blast radius was above 20, the model's average error was -22.6 files;
for files with no co-change at all, it predicted 3.65 on average.

## Ten largest errors
| snapshot   | file                                |   actual |   predicted |   past co-change files |   fan-in |
|:-----------|:------------------------------------|---------:|------------:|-----------------------:|---------:|
| 2026-05-09 | src/script/script.h                 |       89 |        6.43 |                     18 |      103 |
| 2025-11-10 | src/net_processing.cpp              |      130 |       51.89 |                    127 |        0 |
| 2024-08-17 | src/bench/logging.cpp               |       80 |        2.14 |                     12 |        0 |
| 2025-11-10 | src/test/validation_block_tests.cpp |       84 |       14.07 |                     22 |        0 |
| 2025-11-10 | src/wallet/wallet.h                 |       95 |       26.71 |                     74 |       55 |
| 2026-02-08 | src/logging.h                       |       79 |       11.2  |                     14 |       75 |
| 2026-02-08 | src/util/fs_helpers.cpp             |       75 |        7.2  |                     60 |        0 |
| 2026-05-09 | src/rpc/mining.h                    |       66 |        0.24 |                      0 |        2 |
| 2026-05-09 | src/httpserver.h                    |       67 |        1.34 |                      4 |        7 |
| 2025-11-10 | src/test/fuzz/util.h                |       82 |       17.61 |                     20 |      111 |

## Feature importance
| Feature                              |   Importance |
|:-------------------------------------|-------------:|
| historical_commit_count_365d         |       0.2685 |
| fan_out                              |       0.2672 |
| pagerank                             |       0.1255 |
| days_since_last_change               |       0.1124 |
| historical_cochange_event_count_365d |       0.1012 |
| historical_cochange_file_count_365d  |       0.0692 |
| historical_corrective_count_365d     |       0.0245 |
| fan_in                               |       0.0158 |
| betweenness                          |       0.0158 |
