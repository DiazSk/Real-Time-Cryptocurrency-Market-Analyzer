with both_sources as (
    select
        crypto_id,
        symbol,
        bucket,
        pipeline_close,
        exchange_close,
        pipeline_volume,
        exchange_volume,
        (pipeline_close - exchange_close) / exchange_close * 100 as close_diff_pct,
        pipeline_volume / nullif(exchange_volume, 0) as volume_ratio
    from {{ ref('int_candles_unified') }}
    where pipeline_close is not null and exchange_close is not null
)

select
    *,
    coalesce(abs(close_diff_pct) <= 0.05 and abs(volume_ratio - 1) <= 0.05, false) as agrees
from both_sources
