{{ config(materialized='incremental', unique_key=['crypto_id', 'bucket']) }}

-- Returns are computed over the full history (in int_returns_1m) before the incremental filter,
-- so the first minute of each run still sees its previous minute.
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
    r.log_return
from {{ ref('int_candles_unified') }} u
join {{ ref('int_returns_1m') }} r using (crypto_id, bucket)
{% if is_incremental() %}
where u.bucket >= (select max(bucket) - interval '2 hours' from {{ this }})
{% endif %}
