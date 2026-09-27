# Sub-project 4: Written Market Analysis — Design

**Date:** 2026-09-27
**Status:** Approved in chat. The owner asked for implementation to start right away.
**Branch:** `feat/market-analysis`

## Context and goal

Sub-project 3 built dbt marts over 911,759 one-minute candles covering 90 days for 8 pairs. This sub-project turns them into a written analysis that shows data-analyst skills:

- a clear question for each section;
- a baseline or null hypothesis for every claim;
- uncertainty on every estimate;
- charts that answer the question;
- honest caveats.

It has two audiences. A recruiter skims `analysis/README.md` in about 2 minutes. An interviewer digs into the notebook.

**Decisions made in chat:**

- **Format:** a Jupyter notebook, committed with its outputs, plus a one-page summary. This was option A.
- **Rigor:** descriptive statistics, plus baselines, bootstrap confidence intervals and significance tests. This was option B. GARCH and other models are out of scope.

**Success means:**

1. `make analysis` rebuilds dbt and re-executes the notebook top to bottom, producing the same numbers every run (fixed seeds).
2. Every finding in `analysis/README.md` is stated as "estimate, 95% CI, versus baseline", and a null result is reported as null.
3. Every helper in `analysis/stats.py` has a known-answer unit test that runs in CI.
4. The main README's Results rows are replaced with the baseline-compared findings.

## Verified facts (2026-09-27)

- **Coinbase `/products` `quote_increment`** (one price tick):

  | Pair | Tick |
  |---|---|
  | ADA-USD, DOGE-USD, POL-USD | 0.00001 |
  | AVAX-USD | 0.001 |
  | BTC-USD, ETH-USD, SOL-USD | 0.01 |
  | XRP-USD | 0.0001 |

- **Dependencies:** a dry run of pandas 3.0.6, numpy 2.5.3, scipy 1.18.1, matplotlib 3.11.2, nbclient 0.11.0, nbconvert 7.17.1 and ipykernel 7.3.0 into the main venv changes no pinned package. They go in `requirements-analysis.txt`.
- **Existing marts:** `mart_volatility_hourly` has about 14.5k usable hour pairs, and `mart_signals` has 4,391 signals.

## Section 1: Structure and data flow

```
analysis/
  market_analysis.ipynb   committed with outputs, so GitHub renders it
  stats.py                pure numpy/scipy helpers, unit-tested
  charts/*.png            written by the notebook
  README.md               2-minute summary: 4 findings, 4 charts, caveats
requirements-analysis.txt
```

- **Queries.** The notebook queries `analytics.*` through psycopg2 using the `.env` connection settings, the same way dbt does. Heavy aggregation stays in SQL; pandas only receives what the statistics need.
- **New mart `mart_minute_outcomes`** (table). One row per symbol-minute with a valid return, a valid 15-minute forward return and at least 30 prior returns. It has the same continuation definition as `mart_signals`. Columns:
  - `crypto_id`, `symbol`, `bucket`, `day`;
  - `log_return`, `fwd_return_15m`, `z_score`;
  - `is_signal`, which is true when |z| > 4;
  - `continued_15m`.
- **Excluding zero returns.** Minutes where `log_return = 0` or `fwd_return_15m = 0` are excluded. On coarse-tick pairs they would mechanically inflate "reverted".
- **What the notebook pulls.** It doesn't pull 911k rows. It pulls per-symbol-day aggregates from this mart (continued count, total, and the sum of signed forward return) for signals and for all minutes. The day-block bootstrap resamples those.
- **New dbt seed `product_ticks.csv`:** `symbol,coinbase_product,quote_increment,source`, holding the verified values above. Its tests are `unique` and `not_null` on `symbol`.
- **`make analysis`:**
  1. `make dbt`;
  2. `jupyter nbconvert --to notebook --execute --inplace analysis/market_analysis.ipynb`.
- **Fixed seeds.** Every random draw uses `numpy.random.default_rng(20260927)`.

## Section 2: The four analyses

### Q1. Do volatile hours follow volatile hours? (`mart_volatility_hourly`)

- **Data:** hours with at least 30 valid returns.
- **Deseasonalize:** divide `realized_vol` by that pair's mean for the same UTC hour, then take the log.
- **Statistic:** the autocorrelation function (ACF) at lags 1–24, per pair. Lag k pairs only hours exactly k hours apart.
- **Null:** shuffle hours within each pair 1,000 times and take the 2.5–97.5 percentile band.
- **Uncertainty:** a lag-1 CI from a moving-block bootstrap that resamples whole days (blocks of 24 hours) 1,000 times.
- **Chart:** `charts/q1_volatility_acf.png`, small multiples of ACF by lag with the null band shaded.
- **Headline:** the median lag-1 ACF across pairs, the per-pair range with CIs, and how many pairs clear the null band.

### Q2. When in the week is each market most active? (`mart_volatility_hourly`)

- **Normalize:** each hour's `realized_vol` divided by that pair's overall mean.
- **Heatmap:** ISO weekday × UTC hour, averaged across pairs → `charts/q2_seasonality_heatmap.png`.
- **Test:** Kruskal-Wallis across the 24 UTC hours, per pair.
- **Effect size:** the ratio of the peak hour's mean to the quietest hour's mean, with a day-block bootstrap CI.
- **Caveat:** about 13 samples per weekday-hour cell.

### Q3. After an extreme move, does the price continue or revert? (`mart_minute_outcomes`)

- **Rates:** the continuation rate for signals and the continuation rate for all minutes, per severity and per pair. Each gets a day-block bootstrap CI.
- **Difference:** signal rate minus baseline rate, with a bootstrap CI, plus a two-proportion z-test.
- **Magnitude:** the mean signed 15-minute forward return in the move's direction, in basis points, with a bootstrap CI.
- **Multiple comparisons:** the per-pair tests get a Holm correction.
- **Chart:** `charts/q3_continuation.png`, rates with CIs, signals versus baseline, by severity.

### Q4. How well does the pipeline agree with the exchange? (`mart_pipeline_vs_exchange_summary` + `product_ticks`)

- **Agreement:** close-price and volume agreement per pair, with Wilson 95% intervals. There are only about 132–184 stream-built minutes per pair.
- **Tick-size explanation:** compute each pair's tick as a percentage of its price (median close). Then show a scatter of tick % against close agreement, and the Spearman correlation across the 8 pairs.
- **Chart:** `charts/q4_agreement_ticks.png`.

### Write-up rule

Every finding is stated as "estimate [95% CI] vs baseline". The notebook's last cell prints a findings table, and the summary copies those numbers verbatim.

## Section 3: Tests, CI, README

- **`tests/analysis/test_stats.py`** has one known-answer test per helper:
  - `bootstrap_ci`: coverage of a known mean with a fixed seed;
  - `block_bootstrap_ci`: resamples whole blocks;
  - `wilson_ci`: matches the textbook value for 8/10 → [0.49, 0.94];
  - `holm`: matches hand-computed adjusted p-values;
  - `acf`: recovers φ≈0.7 from a simulated AR(1);
  - `shuffle_null_band`: brackets 0 for white noise;
  - `two_proportion_z`: matches a hand-computed value.
- **dbt:**
  - `mart_minute_outcomes` has `unique_combination_of_columns` on `(crypto_id, bucket)`;
  - a unit test checks that zero returns are excluded and that `is_signal` is true only when |z| > 4;
  - the seed has its tests.
- **CI:**
  - the `python` job also installs `requirements-analysis.txt`;
  - the `analytics` job covers the new mart and seed;
  - the notebook itself is **not** executed in CI, because the fixture is too small for meaningful statistics. The helpers are unit-tested, and the notebook is re-executed locally with `make analysis` before committing.
- **`analysis/README.md`:**
  - a disclaimer: descriptive market statistics, not trading or investment advice;
  - for each question: the question, a one-line answer with CI and baseline, the chart, and the caveat;
  - how to reproduce.
- **Main README:** the analysis rows in Results become the baseline-compared findings, linked to `analysis/README.md`.

## Out of scope

- GARCH and other volatility models.
- Trading strategies or backtests.
- Dashboards.
- Executing the notebook in CI.
