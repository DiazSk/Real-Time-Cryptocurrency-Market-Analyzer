select
    crypto_id,
    bucket,
    open,
    high,
    low,
    close,
    volume
from {{ source('pipeline', 'coinbase_candles_1m') }}
