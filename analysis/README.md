# Market analysis: four questions, answered with baselines

This analysis uses about 911k one-minute candles for 8 Coinbase pairs (BTC, ETH, SOL, XRP, ADA, AVAX, DOGE and POL), covering 90 days from 2026-06-29 to 2026-09-27. The data comes from the [dbt marts](../analytics/).

- Every number below has a **95% confidence interval** and a **baseline or null hypothesis**.
- Minutes within a day aren't independent, so the intervals resample **whole days** (a block bootstrap).
- Null results are reported as null.

**Full method, code and tables:** [`market_analysis.ipynb`](market_analysis.ipynb)

> Descriptive market statistics for a data-engineering portfolio project. Not trading or investment advice.

## 1. Volatile hours follow volatile hours

![Autocorrelation of hourly volatility](charts/q1_volatility_acf.png)

- **Finding:** the lag-1 autocorrelation of hourly volatility is **0.76** (median across pairs; 0.61 to 0.85 per pair, with 95% CIs spanning 0.42 to 0.88). That clears the 95% shuffle null for **all 8 pairs**. The null's upper bound is about 0.04 for most pairs and 0.12 at most (POL, with fewer hours).
- **Method:** each hour is first divided by its pair's average for the same UTC hour. This removes the daily rhythm, which on its own would make neighbouring hours look alike.
- **Caveat:** the correlation is still 0.17 to 0.60 at 24 hours. Volatility regimes last for days, not just hours.

## 2. Markets are busiest around 14:00 UTC

![Volatility by weekday and hour](charts/q2_seasonality_heatmap.png)

- **Finding:** volatility at the peak hour (**14:00 UTC**, just after the US market opens at 13:30 UTC) is **1.80x** the quietest hour (06:00 UTC), with a 95% CI of **[1.60, 1.99]**.
- **Test:** Kruskal-Wallis across the 24 UTC hours, Holm-corrected. The hour effect is clear (p < 0.001) for 7 of 8 pairs and only marginal for POL (p = 0.044). The test assumes independent hours, which Q1 shows they aren't, so POL's result shouldn't be read as significant.
- **Weekday vs weekend is inconclusive:** weekday hours are 1.26x as volatile as weekend hours, but the 95% CI of [0.98, 1.61] includes 1. Thirteen weeks aren't enough to tell.
- **Caveat:** each weekday-hour cell has only about 13 samples. Single bright cells, such as Saturday 05:00, are one-off events, not patterns.

## 3. Extreme moves continue less often than ordinary minutes

![Continuation of extreme moves](charts/q3_continuation.png)

A **signal** here is a 1-minute move with |z| > 4. It's the SQL version of the pipeline's Flink detector.

- **Frequency:** **45.2%** of the 3,856 signals kept going the same direction 15 minutes later, 95% CI [42.9%, 47.4%]. The baseline, across the 652,357 scored minutes that aren't signals, is **49.5%**, 95% CI [49.3%, 49.7%]. The difference is **−4.2 points**, 95% CI [−6.5, −2.0].
- **Per pair:** the difference is significant in 3 of 8 pairs (BTC, ETH and XRP) with a two-proportion z-test and Holm correction. That test assumes independent minutes, so the pooled bootstrap CI above is the more reliable number.
- **Size:** the mean 15-minute return in the signal's direction is not distinguishable from zero: +2.1 bps, 95% CI [−1.6, +6.5], against +0.10 bps for ordinary minutes. The direction reverses more often than usual, but there's no measurable average reversal.
- **Caveats:**
  - Minutes with a zero return now or 15 minutes later are excluded on both sides, because on thin pairs a flat price would otherwise count as "reverted".
  - The HIGH severity group alone (n = 352) overlaps the baseline.

## 4. The streaming pipeline matches the exchange on liquid pairs

![Pipeline vs exchange agreement](charts/q4_agreement_ticks.png)

- **Finding:** these are minutes the stream built by itself. For **BTC, ETH, SOL and XRP**, the close price agrees with Coinbase's official candle on **99.5% to 100%** of minutes, and volume is within 5% on **90.2% to 95.7%**. That covers about 183 to 184 minutes per pair; the Wilson intervals are in the notebook.
- **A hypothesis ruled out:** tick-size rounding doesn't explain the close-price misses on thin pairs.
  - Even at each pair's lowest price in the 90 days, the largest price tick is **0.017%** of price (AVAX), so a one-tick difference can never exceed the 0.05% tolerance.
  - A rank correlation between tick size and agreement is shown in the notebook, but with 8 pairs it's underpowered (ρ = −0.37, p = 0.37) and only secondary.
- **Open question:** POL's close-price misses (31% of its minutes) remain unexplained.

## Limitations

- **Dependence across days.** The CIs resample whole days, but volatility persists for days (Q1), so they're slightly narrow. Re-running with week-long blocks changes no conclusion.
- **Independence assumptions.** The Kruskal-Wallis and per-pair z-tests assume independent hours or minutes, so their p-values are optimistic. That's why the pooled bootstrap CIs are the headline numbers.
- **Scope.** One exchange, 90 days (June to September 2026). This isn't a general claim about crypto markets.

## Reproduce

With the stack up and the backfill loaded:

```bash
make analysis
```

It rebuilds the dbt marts, then re-executes the notebook top to bottom, rewriting the charts and the findings cell. The random seed is fixed, so the numbers above reproduce exactly. The statistics helpers in [`stats.py`](stats.py) have known-answer tests in [`tests/analysis/`](../tests/analysis/).
