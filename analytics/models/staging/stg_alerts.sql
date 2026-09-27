select
    crypto_id,
    window_start as bucket,
    alert_type,
    severity,
    z_score,
    price_change_pct
from {{ source('pipeline', 'price_alerts') }}
