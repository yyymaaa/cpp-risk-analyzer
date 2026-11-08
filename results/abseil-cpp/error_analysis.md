# Error analysis: abseil-cpp (held-out test period)

Test rows: 5927 · rows with any co-change: 21.1%

## By file kind
| kind   |   rows |   mean_actual |   mean_predicted |   mae |   bias |
|:-------|-------:|--------------:|-----------------:|------:|-------:|
| prod   |   3799 |          3.06 |             2.16 |  3.97 |  -0.91 |
| test   |   1705 |          2.98 |             1.28 |  3.59 |  -1.7  |
| tool   |    423 |          3.04 |             1.13 |  3.75 |  -1.91 |

## By size of the actual blast radius
| bucket   |   rows |   mean_actual |   mean_predicted |   mae |   bias |
|:---------|-------:|--------------:|-----------------:|------:|-------:|
| 0        |   4675 |          0    |             1.47 |  1.47 |   1.47 |
| 1-5      |    463 |          2.33 |             3.22 |  2.64 |   0.89 |
| 6-20     |    469 |         11.9  |             3.17 |  9.26 |  -8.73 |
| >20      |    320 |         35.44 |             3.1  | 32.34 | -32.34 |

*bias = mean(predicted − actual): negative means the model under-predicts.*

Summary: for files whose real blast radius was above 20, the model's average error was -32.3 files;
for files with no co-change at all, it predicted 1.47 on average.

## Ten largest errors
| snapshot   | file                                                |   actual |   predicted |   past co-change files |   fan-in |
|:-----------|:----------------------------------------------------|---------:|------------:|-----------------------:|---------:|
| 2025-02-14 | absl/strings/str_format.h                           |       66 |        4.06 |                      0 |       36 |
| 2025-02-14 | absl/status/status.cc                               |       63 |        1.35 |                      0 |        0 |
| 2025-02-14 | absl/strings/str_cat.h                              |       71 |       11.09 |                      6 |       80 |
| 2025-02-14 | absl/strings/cord.cc                                |       63 |        3.19 |                      2 |        0 |
| 2026-02-09 | absl/container/internal/common.h                    |       62 |        2.79 |                     14 |        8 |
| 2025-02-14 | absl/strings/numbers.h                              |       60 |        1.96 |                      6 |       18 |
| 2025-02-14 | absl/strings/str_replace.h                          |       59 |        1.15 |                      0 |        9 |
| 2026-08-08 | absl/container/internal/unordered_set_lookup_test.h |       60 |        2.37 |                     20 |        4 |
| 2025-02-14 | absl/strings/escaping.h                             |       59 |        1.53 |                      0 |       11 |
| 2025-02-14 | absl/strings/strip.h                                |       59 |        2.27 |                      0 |       19 |

## Feature importance
| Feature                              |   Importance |
|:-------------------------------------|-------------:|
| historical_cochange_event_count_365d |       0.2483 |
| pagerank                             |       0.1772 |
| days_since_last_change               |       0.1739 |
| historical_cochange_file_count_365d  |       0.1016 |
| fan_out                              |       0.1008 |
| betweenness                          |       0.066  |
| historical_commit_count_365d         |       0.065  |
| fan_in                               |       0.0452 |
| historical_corrective_count_365d     |       0.0221 |
