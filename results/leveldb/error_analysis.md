# Error analysis: leveldb (held-out test period)

Test rows: 1584 · rows with any co-change: 0.3%

## By file kind
| kind   |   rows |   mean_actual |   mean_predicted |   mae |   bias |
|:-------|-------:|--------------:|-----------------:|------:|-------:|
| prod   |   1152 |          0.02 |             0.55 |  0.56 |   0.53 |
| test   |    360 |          0    |             0.05 |  0.05 |   0.05 |
| tool   |     72 |          0    |             0.29 |  0.29 |   0.29 |

## By size of the actual blast radius
| bucket   |   rows |   mean_actual |   mean_predicted |   mae |   bias |
|:---------|-------:|--------------:|-----------------:|------:|-------:|
| 0        |   1579 |             0 |             0.42 |  0.42 |   0.42 |
| 1-5      |      5 |             4 |             0.77 |  3.23 |  -3.23 |

*bias = mean(predicted − actual): negative means the model under-predicts.*

Summary: for files whose real blast radius was above 20, the model's average error was +nan files;
for files with no co-change at all, it predicted 0.42 on average.

## Ten largest errors
| snapshot   | file                    |   actual |   predicted |   past co-change files |   fan-in |
|:-----------|:------------------------|---------:|------------:|-----------------------:|---------:|
| 2025-07-07 | include/leveldb/slice.h |        0 |       11.33 |                      4 |       20 |
| 2025-04-08 | include/leveldb/slice.h |        0 |        9.02 |                      4 |       20 |
| 2025-10-05 | util/env_posix.cc       |        0 |        6.94 |                      4 |        0 |
| 2025-10-05 | util/env_windows.cc     |        0 |        6.37 |                      4 |        0 |
| 2024-01-14 | port/port_stdcxx.h      |        0 |        5.86 |                      6 |        1 |
| 2024-01-14 | table/table_test.cc     |        0 |        5.8  |                      6 |        0 |
| 2025-10-05 | util/hash.cc            |        0 |        5.39 |                      4 |        0 |
| 2024-01-14 | benchmarks/db_bench.cc  |        0 |        5.37 |                      6 |        0 |
| 2025-10-05 | include/leveldb/slice.h |        0 |        4.73 |                      4 |       20 |
| 2026-01-03 | include/leveldb/slice.h |        0 |        4.7  |                      4 |       20 |

## Feature importance
| Feature                              |   Importance |
|:-------------------------------------|-------------:|
| pagerank                             |       0.2603 |
| days_since_last_change               |       0.2504 |
| fan_out                              |       0.1444 |
| historical_cochange_event_count_365d |       0.0886 |
| historical_cochange_file_count_365d  |       0.088  |
| historical_commit_count_365d         |       0.0597 |
| betweenness                          |       0.0506 |
| fan_in                               |       0.0292 |
| historical_corrective_count_365d     |       0.0288 |
