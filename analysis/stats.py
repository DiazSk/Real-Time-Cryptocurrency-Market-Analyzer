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
