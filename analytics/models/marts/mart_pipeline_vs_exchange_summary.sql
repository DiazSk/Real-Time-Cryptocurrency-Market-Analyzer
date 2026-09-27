select
    crypto_id,
    symbol,
    count(*) as n_minutes,
    avg(case when agrees then 1.0 else 0.0 end) as pct_agree,
    avg(abs(close_diff_pct)) as avg_abs_close_diff_pct,
    percentile_cont(0.5) within group (order by volume_ratio) as median_volume_ratio
from {{ ref('mart_pipeline_vs_exchange') }}
group by 1, 2
