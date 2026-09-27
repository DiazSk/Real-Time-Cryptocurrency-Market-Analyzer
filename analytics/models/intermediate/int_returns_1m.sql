with ordered as (
    select
        crypto_id,
        bucket,
        close,
        lag(bucket) over w as prev_bucket,
        lag(close) over w as prev_close
    from {{ ref('int_candles_unified') }}
    window w as (partition by crypto_id order by bucket)
)

select
    crypto_id,
    bucket,
    case when prev_bucket = bucket - interval '1 minute' then ln(close / prev_close)::double precision end as log_return
from ordered
