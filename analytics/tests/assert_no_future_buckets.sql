select *
from {{ ref('fct_candles_1m') }}
where bucket > now() + interval '1 minute'
