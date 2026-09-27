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
    assert acf(x, 2)[1] == pytest.approx(-1.0)  # lag 2: (1,-1), (2,-2), (3,-3)


def test_shuffle_null_band_brackets_zero_for_white_noise():
    lo, hi = shuffle_null_band(rng().normal(size=2000), 2, n=200, rng=rng())
    assert (lo < 0).all() and (hi > 0).all()
