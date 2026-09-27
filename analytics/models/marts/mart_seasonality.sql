select
    crypto_id,
    symbol,
    extract(isodow from hour_start)::int as weekday,
    extract(hour from hour_start)::int as hour_utc,
    avg(realized_vol) as avg_realized_vol,
    avg(volume) as avg_volume,
    count(*) as n_hours
from {{ ref('mart_volatility_hourly') }}
where n_returns >= 30
group by 1, 2, 3, 4
