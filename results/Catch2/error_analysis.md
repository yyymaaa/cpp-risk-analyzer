# Error analysis: Catch2 (held-out test period)

Test rows: 2680 · rows with any co-change: 9.6%

## By file kind
| kind   |   rows |   mean_actual |   mean_predicted |   mae |   bias |
|:-------|-------:|--------------:|-----------------:|------:|-------:|
| prod   |   1951 |          0.71 |             1.55 |  1.86 |   0.84 |
| test   |    652 |          0.39 |             1.1  |  1.39 |   0.71 |
| tool   |     77 |          0.44 |             1.9  |  2.14 |   1.46 |

## By size of the actual blast radius
| bucket   |   rows |   mean_actual |   mean_predicted |   mae |   bias |
|:---------|-------:|--------------:|-----------------:|------:|-------:|
| 0        |   2423 |          0    |             1.34 |  1.34 |   1.34 |
| 1-5      |    141 |          2.44 |             2.8  |  2.38 |   0.36 |
| 6-20     |    113 |         10.85 |             1.96 |  9.02 |  -8.89 |
| >20      |      3 |         32    |             6.09 | 25.91 | -25.91 |

*bias = mean(predicted − actual): negative means the model under-predicts.*

Summary: for files whose real blast radius was above 20, the model's average error was -25.9 files;
for files with no co-change at all, it predicted 1.34 on average.

## Ten largest errors
| snapshot   | file                                            |   actual |   predicted |   past co-change files |   fan-in |
|:-----------|:------------------------------------------------|---------:|------------:|-----------------------:|---------:|
| 2026-02-08 | src/catch2/internal/catch_run_context.cpp       |       41 |        6.69 |                     39 |        0 |
| 2026-02-08 | src/catch2/catch_all.hpp                        |       28 |        5.42 |                     12 |        0 |
| 2025-08-12 | src/catch2/catch_session.cpp                    |        4 |       25.03 |                     13 |        0 |
| 2026-02-08 | src/catch2/generators/catch_generators.hpp      |       27 |        6.18 |                      2 |       20 |
| 2025-08-12 | src/catch2/internal/catch_istream.cpp           |        0 |       19.33 |                     12 |        0 |
| 2024-11-15 | src/catch2/internal/catch_reporter_registry.hpp |        0 |       19.15 |                      0 |        7 |
| 2025-05-14 | src/catch2/internal/catch_reporter_registry.hpp |        0 |       19.15 |                      0 |        7 |
| 2025-02-13 | src/catch2/internal/catch_reporter_registry.hpp |        0 |       19.15 |                      0 |        7 |
| 2025-02-13 | src/catch2/matchers/catch_matchers_contains.hpp |       18 |        0.13 |                      0 |        2 |
| 2025-05-14 | src/catch2/reporters/catch_reporter_console.cpp |       19 |        2.01 |                      1 |        0 |

## Feature importance
| Feature                              |   Importance |
|:-------------------------------------|-------------:|
| pagerank                             |       0.3151 |
| days_since_last_change               |       0.1945 |
| fan_out                              |       0.1168 |
| historical_cochange_file_count_365d  |       0.1054 |
| historical_cochange_event_count_365d |       0.1029 |
| historical_commit_count_365d         |       0.0744 |
| betweenness                          |       0.0495 |
| fan_in                               |       0.0255 |
| historical_corrective_count_365d     |       0.016  |
