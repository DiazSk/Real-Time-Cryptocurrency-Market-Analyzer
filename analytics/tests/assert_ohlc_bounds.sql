-- Every candle's low/high must bracket its open and close, and volume can't be negative.
select *
from {{ ref('fct_candles_1m') }}
where low > least(open, close) or high < greatest(open, close) or volume < 0
