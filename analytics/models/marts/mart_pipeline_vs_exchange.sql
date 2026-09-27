-- Reads fct_candles_1m (not the intermediate view) so has_repaired_trades survives raw_trades'
-- 7-day retention: the incremental fact table keeps the flag computed when the minute was built.
with both_sources as (
    select
        crypto_id,
        symbol,
        bucket,
        has_repaired_trades,
        pipeline_close,
        exchange_close,
        pipeline_volume,
        exchange_volume,
        (pipeline_close - exchange_close) / exchange_close * 100 as close_diff_pct,
        pipeline_volume / nullif(exchange_volume, 0) as volume_ratio
    from {{ ref('fct_candles_1m') }}
    where pipeline_close is not null and exchange_close is not null
)

select
    *,
    coalesce(abs(close_diff_pct) <= 0.05, false) as close_agrees,
    coalesce(abs(volume_ratio - 1) <= 0.05, false) as volume_agrees,
    coalesce(abs(close_diff_pct) <= 0.05 and abs(volume_ratio - 1) <= 0.05, false) as agrees
from both_sources
