-- Pipeline candles win where they exist (they're what the product computes); exchange candles
-- fill the 90-day history and any minute the pipeline missed.
select
    coalesce(p.crypto_id, e.crypto_id) as crypto_id,
    s.symbol,
    coalesce(p.bucket, e.bucket) as bucket,
    case when p.crypto_id is not null then p.open else e.open end as open,
    case when p.crypto_id is not null then p.high else e.high end as high,
    case when p.crypto_id is not null then p.low else e.low end as low,
    case when p.crypto_id is not null then p.close else e.close end as close,
    case when p.crypto_id is not null then p.volume else e.volume end as volume,
    case when p.crypto_id is not null then 'pipeline' else 'exchange' end as source,
    p.close as pipeline_close,
    e.close as exchange_close,
    p.volume as pipeline_volume,
    e.volume as exchange_volume,
    greatest(p.loaded_at, e.loaded_at) as loaded_at  -- when this minute last changed in either source
from {{ ref('stg_pipeline_candles') }} p
full outer join {{ ref('stg_exchange_candles') }} e
    on p.crypto_id = e.crypto_id and p.bucket = e.bucket
join {{ ref('stg_symbols') }} s
    on s.crypto_id = coalesce(p.crypto_id, e.crypto_id)
