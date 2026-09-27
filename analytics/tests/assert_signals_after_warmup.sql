-- A signal needs at least 30 prior returns in its 60-minute lookback.
select *
from {{ ref('mart_signals') }}
where n_prior < 30
