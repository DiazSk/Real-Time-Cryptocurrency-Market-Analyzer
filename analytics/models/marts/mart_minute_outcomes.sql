-- Baseline for the continuation question: every minute scored with the same rule as mart_signals
-- (z of the return against the previous 60 returns, >= 30 of them), plus whether the move continued
-- 15 minutes later. Zero returns on either side are dropped: on coarse-tick pairs a flat price is
-- common and would mechanically count as "did not continue".
with scored as (
    select
        crypto_id,
        symbol,
        bucket,
        close,
        volume,
        log_return,
        avg(log_return) over lookback as mean_60,
        stddev_samp(log_return) over lookback as sd_60,
        count(log_return) over lookback as n_prior,
        lead(close, 15) over fwd as close_15,
        lead(bucket, 15) over fwd as bucket_15
    from {{ ref('fct_candles_1m') }}
    window
        lookback as (partition by crypto_id order by bucket rows between 60 preceding and 1 preceding),
        fwd as (partition by crypto_id order by bucket)
),

outcomes as (
    select
        crypto_id,
        symbol,
        bucket,
        log_return,
        (log_return - mean_60) / nullif(sd_60, 0) as z_score,
        case when bucket_15 = bucket + interval '15 minutes' then ln(close_15 / close)::double precision end as fwd_return_15m
    from scored
    where log_return is not null and n_prior >= 30 and volume > 0
)

select
    crypto_id,
    symbol,
    bucket,
    (bucket at time zone 'UTC')::date as day,
    log_return,
    fwd_return_15m,
    z_score,
    coalesce(abs(z_score) > 4, false) as is_signal,
    sign(fwd_return_15m) = sign(log_return) as continued_15m
from outcomes
where fwd_return_15m is not null and log_return <> 0 and fwd_return_15m <> 0
