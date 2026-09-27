# Market Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (native, as chosen for the previous sub-projects). Steps use checkbox (`- [ ]`) syntax.

**Goal:** A reproducible notebook plus a one-page summary answering 4 questions, each with baselines, 95% CIs and honest caveats.

**Architecture:**
- **SQL work stays in dbt.** A new `mart_minute_outcomes` and a `product_ticks` seed.
- **Statistics live in `analysis/stats.py`**, as pure numpy/scipy code with known-answer tests.
- **The notebook** (`analysis/market_analysis.ipynb`) queries per-day aggregates, calls `stats.py`, writes the PNGs and prints the findings table.
- **`make analysis`** rebuilds and re-executes it.

**Tech Stack:** pandas 3.0.6, numpy 2.5.3, scipy 1.18.1, matplotlib 3.11.2, nbclient/nbconvert, ipykernel, psycopg2, dbt 1.12.

**Spec:** `docs/superpowers/specs/2026-09-27-market-analysis-design.md`

## Global Constraints

- Commits carry no AI attribution (`CLAUDE.md`, which is now local-only).
- Seed `numpy.random.default_rng(20260927)`; 1,000 shuffles; 2,000 bootstrap resamples; alpha 0.05.
- Continuation: `sign(fwd_return_15m) = sign(log_return)`, where minutes with a zero return on either side are excluded. A signal is `|z| > 4`, using the previous 60 returns with at least 30 of them.
- Findings are stated as "estimate [95% CI] vs baseline". A null result is reported as null.
- The analysis carries a disclaimer: descriptive statistics, not trading or investment advice.

## Review Focus

1. **A pair with no signals at some severity.** The rates must become NaN and be reported as "n/a", not crash or divide by zero. Pinned by `bootstrap_ci` on an empty input, and handled in the notebook.
2. **Hours missing inside a pair's series.** The lagged autocorrelation must only pair hours exactly k apart, not neighbouring rows. Pinned by `test_acf_ignores_nan_gaps`.
3. **Clustered signals on the same day.** The CI must come from the day-block bootstrap, not the naive one. Pinned by `test_block_bootstrap_is_wider_for_clustered_data`.
4. **Zero-return minutes on coarse-tick pairs.** They must be excluded on both sides. Pinned by the dbt unit test.
5. **The summary quoting a number the notebook didn't produce.** Guarded by the executor copying numbers from the notebook's final cell.

---

### Task 1: `analysis/stats.py` (TDD)

**Files:** create `analysis/__init__.py` (empty), `analysis/stats.py`, `tests/analysis/test_stats.py`, `requirements-analysis.txt`.

- [ ] **Step 1:** Install the dependencies (`venv/bin/pip install -r requirements-analysis.txt`).
- [ ] **Step 2:** Write the tests below and run them. Expected result: `ModuleNotFoundError: analysis.stats`.

```python
import numpy as np
import pytest

from analysis.stats import (
    acf, block_bootstrap_ci, bootstrap_ci, holm, shuffle_null_band, two_proportion_z, wilson_ci,
)


def rng():
    return np.random.default_rng(20260927)


def test_bootstrap_ci_covers_the_true_mean():
    x = rng().normal(5, 1, 500)
    lo, hi = bootstrap_ci(x, rng=rng())
    assert lo < 5 < hi and 0.1 < hi - lo < 0.3


def test_bootstrap_ci_of_nothing_is_nan():
    lo, hi = bootstrap_ci(np.array([]), rng=rng())
    assert np.isnan(lo) and np.isnan(hi)


def test_block_bootstrap_is_wider_for_clustered_data():
    # 20 days whose minutes all share the day's value: 200 rows, but only 20 independent draws
    days = [np.full(10, v) for v in rng().normal(0, 1, 20)]
    naive = bootstrap_ci(np.concatenate(days), rng=rng())
    block = block_bootstrap_ci(days, lambda rows: rows.mean(), rng=rng())
    assert (block[1] - block[0]) > 2 * (naive[1] - naive[0])


def test_wilson_matches_the_textbook_value():
    lo, hi = wilson_ci(8, 10)
    assert round(lo, 3) == 0.490 and round(hi, 3) == 0.943


def test_holm_adjusts_and_keeps_order():
    assert np.allclose(holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])


def test_two_proportion_z_matches_hand_computation():
    z, p = two_proportion_z(60, 100, 50, 100)
    assert round(z, 3) == 1.421 and round(p, 3) == 0.155


def test_acf_recovers_an_ar1_coefficient():
    r = rng()
    x = np.zeros(20000)
    for t in range(1, len(x)):
        x[t] = 0.7 * x[t - 1] + r.normal()
    assert abs(acf(x, 3)[0] - 0.7) < 0.02


def test_acf_ignores_nan_gaps():
    # a missing hour must not make hours 2 apart look adjacent
    x = np.array([1.0, np.nan, -1.0, 2.0, np.nan, -2.0, 3.0, np.nan, -3.0])
    assert np.isnan(acf(x, 1)[0])  # only 2 true lag-1 pairs: too few to define a correlation
    assert acf(x, 2)[0] == pytest.approx(-1.0)  # (1,-1), (2,-2), (3,-3)


def test_shuffle_null_band_brackets_zero_for_white_noise():
    lo, hi = shuffle_null_band(rng().normal(size=2000), 2, n=200, rng=rng())
    assert (lo < 0).all() and (hi > 0).all()
```

- [ ] **Step 3:** Implement `analysis/stats.py`:

```python
"""Statistics helpers for the market analysis notebook (known-answer tests in tests/analysis/)."""

import numpy as np
from scipy import stats as sps

N_BOOT = 2000


def bootstrap_ci(x, stat=np.mean, n=N_BOOT, alpha=0.05, rng=None):
    """Percentile bootstrap CI of stat(x); (nan, nan) for an empty sample."""
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return float("nan"), float("nan")
    rng = rng or np.random.default_rng()
    draws = [stat(x[rng.integers(0, x.size, x.size)]) for _ in range(n)]
    return tuple(np.quantile(draws, [alpha / 2, 1 - alpha / 2]))


def block_bootstrap_ci(blocks, stat, n=N_BOOT, alpha=0.05, rng=None):
    """Resample whole blocks (e.g. days) with replacement; stat receives the concatenated rows.

    Minutes within a day aren't independent, so resampling days keeps the CI honest.
    """
    blocks = [np.asarray(b) for b in blocks if len(b)]
    if not blocks:
        return float("nan"), float("nan")
    rng = rng or np.random.default_rng()
    draws = [stat(np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), len(blocks))])) for _ in range(n)]
    return tuple(np.quantile(draws, [alpha / 2, 1 - alpha / 2]))


def wilson_ci(k, n, z=1.959964):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def holm(pvalues):
    """Holm-Bonferroni adjusted p-values, returned in the input order."""
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    adjusted = np.minimum(1, np.maximum.accumulate(p[order] * (len(p) - np.arange(len(p)))))
    out = np.empty_like(adjusted)
    out[order] = adjusted
    return out


def two_proportion_z(k1, n1, k2, n2):
    """Pooled two-proportion z-test; returns (z, two-sided p)."""
    pooled = (k1 + k2) / (n1 + n2)
    se = np.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    z = (k1 / n1 - k2 / n2) / se
    return z, 2 * sps.norm.sf(abs(z))


def acf(x, max_lag):
    """Correlation between x[t] and x[t+k] for k = 1..max_lag, using only pairs where both exist.

    x must be on a regular grid (one slot per hour) with NaN for missing slots, so lag k always
    means exactly k hours apart.
    """
    x = np.asarray(x, dtype=float)
    out = []
    for k in range(1, max_lag + 1):
        a, b = x[:-k], x[k:]
        m = np.isfinite(a) & np.isfinite(b)
        out.append(np.corrcoef(a[m], b[m])[0, 1] if m.sum() > 2 else np.nan)
    return np.array(out)


def shuffle_null_band(x, max_lag, n=1000, alpha=0.05, rng=None):
    """ACF band under 'no time structure': shuffle the series n times."""
    rng = rng or np.random.default_rng()
    x = np.asarray(x, dtype=float)
    draws = np.array([acf(rng.permutation(x), max_lag) for _ in range(n)])
    return np.nanquantile(draws, alpha / 2, axis=0), np.nanquantile(draws, 1 - alpha / 2, axis=0)
```

- [ ] **Step 4:** Tests pass. In CI, add `requirements-analysis.txt` to the `python` job's `pip install`. Commit.

### Task 2: dbt `mart_minute_outcomes` and the `product_ticks` seed

- [ ] **Step 1:** Write the unit test `zero_returns_are_excluded_and_signals_flagged`, fed from `fct_candles_1m`:
  - **Input:** 50 minutes. Closes alternate 100/100.01; minute 32 repeats minute 31 (a zero return); minute 33 jumps to 101; from minute 34 the price alternates 101.01/101.
  - **Expected rows:**
    - minute 31: `is_signal` false, `continued_15m` true;
    - minute 33: `is_signal` true, `continued_15m` true;
    - minute 34: `is_signal` false, `continued_15m` false;
    - minute 32 does not appear.

  Run it. Expected result: fail, because the model is missing.
- [ ] **Step 2:** Write `models/marts/mart_minute_outcomes.sql`. It uses the same lookback and forward windows as `mart_signals`, filters to `log_return <> 0`, `fwd_return_15m <> 0` and `n_prior >= 30`, and adds `day = (bucket at time zone 'UTC')::date`.

  Also write `seeds/product_ticks.csv` with the 8 verified increments, plus the schema YAML (a unique combination on `crypto_id, bucket`, and `unique`/`not_null` on the seed's `symbol`).
- [ ] **Step 3:** Run `make dbt`: everything green. Commit.

### Task 3: The notebook, charts and `make analysis`

- [ ] **Step 1:** Build `analysis/market_analysis.ipynb` with these sections:
  - Setup;
  - Q1 through Q4, as the spec describes;
  - Findings table, printing every headline number.
- [ ] **Step 2:** Add the `analysis` Makefile target and run it against the live DB (stack up). Every cell must succeed, and the 4 PNGs must be written.
- [ ] **Step 3:** Commit the notebook with its outputs and charts.

### Task 4: Write-up

- [ ] **Step 1:** Write `analysis/README.md` from the findings cell, including the disclaimer.
- [ ] **Step 2:** Replace the analysis rows in the main README's Results table with the baseline-compared findings, and link them. Commit.
