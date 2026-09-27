-- Agreement over minutes the stream built on its own; REST-repaired minutes are counted separately.
select
    crypto_id,
    symbol,
    count(*) filter (where not has_repaired_trades) as n_minutes,
    count(*) filter (where has_repaired_trades) as n_repaired_minutes,
    avg(case when agrees then 1.0 else 0.0 end) filter (where not has_repaired_trades) as pct_agree,
    avg(case when close_agrees then 1.0 else 0.0 end) filter (where not has_repaired_trades) as pct_close_agree,
    avg(case when volume_agrees then 1.0 else 0.0 end) filter (where not has_repaired_trades) as pct_volume_agree,
    avg(abs(close_diff_pct)) filter (where not has_repaired_trades) as avg_abs_close_diff_pct,
    percentile_cont(0.5) within group (order by volume_ratio) filter (where not has_repaired_trades) as median_volume_ratio
from {{ ref('mart_pipeline_vs_exchange') }}
group by 1, 2
