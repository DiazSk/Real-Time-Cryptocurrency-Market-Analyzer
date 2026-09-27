select
    crypto_id,
    bucket,
    open,
    high,
    low,
    close,
    volume,
    loaded_at
from {{ source('pipeline', 'coinbase_candles_1m') }}
