{{ config(materialized='incremental', unique_key=['crypto_id', 'bucket']) }}

-- Returns are computed over the full history (in int_returns_1m) before the incremental filter,
-- so the first minute of each run still sees its previous minute.
-- Incremental runs reprocess every symbol-day that received rows since the last run (by loaded_at),
-- because backfilled candles arrive with old buckets; a newest-buckets-only filter would skip them.
-- The day after each changed minute is included too, since that minute's successor return changes.
select
    u.crypto_id,
    u.symbol,
    u.bucket,
    u.open,
    u.high,
    u.low,
    u.close,
    u.volume,
    u.source,
    u.pipeline_close,
    u.exchange_close,
    u.pipeline_volume,
    u.exchange_volume,
    r.log_return,
    u.loaded_at,
    u.has_repaired_trades
from {{ ref('int_candles_unified') }} u
join {{ ref('int_returns_1m') }} r using (crypto_id, bucket)
{% if is_incremental() %}
where (u.crypto_id, date_trunc('day', u.bucket)) in (
    select crypto_id, date_trunc('day', bucket + d)
    from {{ ref('int_candles_unified') }}, (values (interval '0'), (interval '1 minute')) as shift(d)
    where loaded_at > (select coalesce(max(loaded_at), '-infinity') from {{ this }})
)
{% endif %}
