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
        lead(close, 5) over fwd as close_5,
        lead(bucket, 5) over fwd as bucket_5,
        lead(close, 15) over fwd as close_15,
        lead(bucket, 15) over fwd as bucket_15,
        lead(close, 60) over fwd as close_60,
        lead(bucket, 60) over fwd as bucket_60
    from {{ ref('fct_candles_1m') }}
    window
        lookback as (partition by crypto_id order by bucket rows between 60 preceding and 1 preceding),
        fwd as (partition by crypto_id order by bucket)
),

signals as (
    select
        *,
        (log_return - mean_60) / nullif(sd_60, 0) as z_score,
        case when bucket_5 = bucket + interval '5 minutes' then ln(close_5 / close)::double precision end as fwd_return_5m,
        case when bucket_15 = bucket + interval '15 minutes' then ln(close_15 / close)::double precision end as fwd_return_15m,
        case when bucket_60 = bucket + interval '60 minutes' then ln(close_60 / close)::double precision end as fwd_return_60m
    from scored
    where log_return is not null and n_prior >= 30 and volume > 0
)

select
    s.crypto_id,
    s.symbol,
    s.bucket,
    s.log_return,
    s.z_score,
    s.n_prior,
    case when s.log_return > 0 then 'PRICE_SPIKE' else 'PRICE_DROP' end as alert_type,
    case when abs(s.z_score) >= 8 then 'HIGH' when abs(s.z_score) >= 6 then 'MEDIUM' else 'LOW' end as severity,
    s.fwd_return_5m,
    s.fwd_return_15m,
    s.fwd_return_60m,
    sign(s.fwd_return_15m) = sign(s.log_return) as continued_15m,
    sign(s.fwd_return_60m) = sign(s.log_return) as continued_60m,
    exists (
        select 1 from {{ ref('stg_alerts') }} a
        where a.crypto_id = s.crypto_id and a.bucket = s.bucket
    ) as flink_alert
from signals s
where abs(s.z_score) > 4
