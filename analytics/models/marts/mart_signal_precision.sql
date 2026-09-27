select
    crypto_id,
    symbol,
    severity,
    count(*) as n_signals,
    avg(case when continued_15m then 1.0 when not continued_15m then 0.0 end) as pct_continued_15m,
    avg(case when continued_60m then 1.0 when not continued_60m then 0.0 end) as pct_continued_60m,
    count(*) filter (where flink_alert) as n_flink_matched
from {{ ref('mart_signals') }}
group by 1, 2, 3
