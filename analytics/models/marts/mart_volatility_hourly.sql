with hourly as (
    select
        crypto_id,
        symbol,
        date_trunc('hour', bucket) as hour_start,
        sqrt(sum(log_return * log_return)) as realized_vol,
        count(log_return) as n_returns,
        sum(volume) as volume
    from {{ ref('fct_candles_1m') }}
    group by 1, 2, 3
)

select
    *,
    case
        when lag(hour_start) over w = hour_start - interval '1 hour' then lag(realized_vol) over w
    end as prev_hour_vol
from hourly
window w as (partition by crypto_id order by hour_start)
