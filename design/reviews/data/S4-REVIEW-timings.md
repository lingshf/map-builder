# S4-REVIEW raw timings (D91, D106, D120)

Raw data for [S4-REVIEW.md §1.4](../S4-REVIEW.md). Host: Windows, Python 3.12, Blender 4.2.23,
frozen RC #56 caches (offline: `network_attempts = 0`, `new_cache_files = 0`). Trees: `git archive` of v0.4.0 and d38d4e8.
Harnesses: [design/bench/cli_time.py](../../bench/cli_time.py) and [design/bench/bl_time.py](../../bench/bl_time.py), unchanged.
Order: for round r in 1..3, for revision in (v0.4.0, d38d4e8): CLI munich and pittsburgh, then Blender munich,
then Blender pittsburgh, 3 runs each. Blender Generate+Export is the elapsed time of both operators in the same run (both FINISHED).

Aggregation: the median of the 3 runs in each round, then the median of the 3 round medians.

## CLI munich

| revision | round | acquire+plan (s) | package (s) | whole Generate (s) |
|---|---|---|---|---|
| v0.4.0 | 1 | 2.516 | 2.399 | 4.948 |
| v0.4.0 | 2 | 3.510 | 3.262 | 7.027 |
| v0.4.0 | 3 | 3.298 | 3.086 | 6.357 |
| d38d4e8 | 1 | 3.556 | 2.702 | 6.610 |
| d38d4e8 | 2 | 3.586 | 2.731 | 6.317 |
| d38d4e8 | 3 | 3.521 | 2.716 | 6.248 |

Each CLI row is already the median of that round's 3 runs, as printed by the harness.

## CLI pittsburgh

| revision | round | acquire+plan (s) | package (s) | whole Generate (s) |
|---|---|---|---|---|
| v0.4.0 | 1 | 12.610 | 21.659 | 38.586 |
| v0.4.0 | 2 | 10.252 | 17.032 | 27.284 |
| v0.4.0 | 3 | 10.144 | 16.703 | 26.816 |
| d38d4e8 | 1 | 11.114 | 15.293 | 26.508 |
| d38d4e8 | 2 | 11.353 | 15.027 | 26.380 |
| d38d4e8 | 3 | 11.543 | 14.902 | 26.444 |

Each CLI row is already the median of that round's 3 runs, as printed by the harness.

## Blender munich

| revision | round | run | Generate (s) | Export (s) | Generate+Export (s) |
|---|---|---|---|---|---|
| v0.4.0 | 1 | 1 | 4.860 | 6.448 | 11.309 |
| v0.4.0 | 1 | 2 | 4.858 | 5.938 | 10.796 |
| v0.4.0 | 1 | 3 | 4.883 | 6.387 | 11.270 |
| v0.4.0 | 2 | 1 | 4.548 | 5.701 | 10.248 |
| v0.4.0 | 2 | 2 | 4.474 | 5.614 | 10.089 |
| v0.4.0 | 2 | 3 | 4.668 | 5.963 | 10.631 |
| v0.4.0 | 3 | 1 | 4.633 | 5.759 | 10.392 |
| v0.4.0 | 3 | 2 | 4.541 | 5.722 | 10.263 |
| v0.4.0 | 3 | 3 | 4.421 | 5.669 | 10.090 |
| d38d4e8 | 1 | 1 | 4.717 | 5.355 | 10.072 |
| d38d4e8 | 1 | 2 | 4.545 | 5.250 | 9.795 |
| d38d4e8 | 1 | 3 | 4.599 | 5.211 | 9.811 |
| d38d4e8 | 2 | 1 | 4.775 | 5.400 | 10.175 |
| d38d4e8 | 2 | 2 | 4.766 | 5.255 | 10.021 |
| d38d4e8 | 2 | 3 | 4.637 | 5.155 | 9.792 |
| d38d4e8 | 3 | 1 | 5.141 | 5.623 | 10.764 |
| d38d4e8 | 3 | 2 | 5.146 | 6.251 | 11.397 |
| d38d4e8 | 3 | 3 | 5.723 | 5.820 | 11.543 |

## Blender pittsburgh

| revision | round | run | Generate (s) | Export (s) | Generate+Export (s) |
|---|---|---|---|---|---|
| v0.4.0 | 1 | 1 | 15.707 | 35.118 | 50.825 |
| v0.4.0 | 1 | 2 | 14.538 | 33.517 | 48.055 |
| v0.4.0 | 1 | 3 | 15.007 | 33.917 | 48.924 |
| v0.4.0 | 2 | 1 | 14.214 | 32.327 | 46.541 |
| v0.4.0 | 2 | 2 | 14.728 | 32.680 | 47.408 |
| v0.4.0 | 2 | 3 | 14.363 | 32.130 | 46.493 |
| v0.4.0 | 3 | 1 | 14.848 | 32.447 | 47.295 |
| v0.4.0 | 3 | 2 | 14.443 | 32.371 | 46.813 |
| v0.4.0 | 3 | 3 | 14.503 | 32.330 | 46.832 |
| d38d4e8 | 1 | 1 | 15.628 | 30.390 | 46.018 |
| d38d4e8 | 1 | 2 | 15.895 | 31.247 | 47.141 |
| d38d4e8 | 1 | 3 | 15.514 | 29.599 | 45.113 |
| d38d4e8 | 2 | 1 | 15.315 | 29.438 | 44.752 |
| d38d4e8 | 2 | 2 | 15.189 | 29.730 | 44.919 |
| d38d4e8 | 2 | 3 | 15.371 | 29.571 | 44.942 |
| d38d4e8 | 3 | 1 | 15.002 | 28.922 | 43.924 |
| d38d4e8 | 3 | 2 | 14.574 | 28.904 | 43.478 |
| d38d4e8 | 3 | 3 | 15.175 | 29.928 | 45.102 |

## Aggregation

| path | preset | measure | v0.4.0 | d38d4e8 | Δ |
|---|---|---|---|---|---|
| CLI | munich | acquire+plan | 3.30 s | 3.56 s | +7.8 % |
| CLI | munich | package | 3.09 s | 2.72 s | -12.0 % |
| CLI | munich | whole Generate | 6.36 s | 6.32 s | -0.6 % |
| CLI | pittsburgh | acquire+plan | 10.25 s | 11.35 s | +10.7 % |
| CLI | pittsburgh | package | 17.03 s | 15.03 s | -11.8 % |
| CLI | pittsburgh | whole Generate | 27.28 s | 26.44 s | -3.1 % |
| Blender | munich | Generate | 4.55 s | 4.77 s | +4.8 % |
| Blender | munich | Export | 5.72 s | 5.25 s | -8.2 % |
| Blender | munich | Generate+Export | 10.26 s | 10.02 s | -2.4 % |
| Blender | pittsburgh | Generate | 14.50 s | 15.31 s | +5.6 % |
| Blender | pittsburgh | Export | 32.37 s | 29.57 s | -8.6 % |
| Blender | pittsburgh | Generate+Export | 46.83 s | 44.92 s | -4.1 % |
