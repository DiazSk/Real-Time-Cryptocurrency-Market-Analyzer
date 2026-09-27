select
    id as crypto_id,
    symbol,
    name,
    coinbase_product,
    is_active
from {{ source('pipeline', 'cryptocurrencies') }}
