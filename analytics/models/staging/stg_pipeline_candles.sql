select
    crypto_id,
    window_start as bucket,
    open_price as open,
    high_price as high,
    low_price as low,
    close_price as close,
    vwap,
    volume,
    trade_count
from {{ source('pipeline', 'price_aggregates_1m') }}
