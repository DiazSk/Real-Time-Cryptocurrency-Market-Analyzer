select
    crypto_id,
    trade_id,
    price,
    size,
    side,
    event_time,
    ingest_time,
    source
from {{ source('pipeline', 'raw_trades') }}
