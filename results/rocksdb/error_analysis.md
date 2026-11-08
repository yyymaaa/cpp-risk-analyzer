# Error analysis: rocksdb (held-out test period)

Test rows: 15497 · rows with any co-change: 20.6%

## By file kind
| kind   |   rows |   mean_actual |   mean_predicted |   mae |   bias |
|:-------|-------:|--------------:|-----------------:|------:|-------:|
| prod   |  11761 |          4.85 |             5.79 |  6.25 |   0.94 |
| test   |   2587 |          6.65 |             8.04 |  8.61 |   1.39 |
| tool   |   1149 |          7.64 |             8.02 |  7.89 |   0.38 |

## By size of the actual blast radius
| bucket   |   rows |   mean_actual |   mean_predicted |   mae |   bias |
|:---------|-------:|--------------:|-----------------:|------:|-------:|
| 0        |  12311 |          0    |             4.02 |  4.02 |   4.02 |
| 1-5      |    542 |          2.9  |            10.53 |  8.3  |   7.63 |
| 6-20     |   1053 |         11.92 |            11.77 |  8.14 |  -0.15 |
| >20      |   1591 |         43.33 |            19.15 | 26.55 | -24.18 |

*bias = mean(predicted − actual): negative means the model under-predicts.*

Summary: for files whose real blast radius was above 20, the model's average error was -24.2 files;
for files with no co-change at all, it predicted 4.02 on average.

## Ten largest errors
| snapshot   | file                                  |   actual |   predicted |   past co-change files |   fan-in |
|:-----------|:--------------------------------------|---------:|------------:|-----------------------:|---------:|
| 2026-07-02 | db/db_impl/db_impl.cc                 |      258 |       94.81 |                    216 |        0 |
| 2026-07-02 | db_stress_tool/db_stress_test_base.cc |      193 |       57.03 |                    283 |        0 |
| 2026-07-02 | db/db_impl/db_impl_secondary.cc       |      154 |       19.67 |                    116 |        0 |
| 2026-07-02 | include/rocksdb/db.h                  |      175 |       45.17 |                    117 |      169 |
| 2026-04-03 | db_stress_tool/db_stress_gflags.cc    |      155 |       29.25 |                    228 |        0 |
| 2026-07-02 | db/c.cc                               |      189 |       66.42 |                    188 |        0 |
| 2026-01-03 | include/rocksdb/c.h                   |      139 |       19.09 |                     32 |        1 |
| 2026-07-02 | tools/db_bench_tool.cc                |      197 |       78.16 |                    196 |        0 |
| 2026-07-02 | db_stress_tool/db_stress_gflags.cc    |      157 |       38.51 |                    266 |        0 |
| 2026-07-02 | include/rocksdb/c.h                   |      159 |       42.01 |                    193 |        1 |

## Feature importance
| Feature                              |   Importance |
|:-------------------------------------|-------------:|
| historical_cochange_event_count_365d |       0.4485 |
| historical_commit_count_365d         |       0.1087 |
| fan_out                              |       0.1035 |
| pagerank                             |       0.099  |
| days_since_last_change               |       0.0906 |
| historical_cochange_file_count_365d  |       0.0674 |
| historical_corrective_count_365d     |       0.0312 |
| betweenness                          |       0.0274 |
| fan_in                               |       0.0237 |
