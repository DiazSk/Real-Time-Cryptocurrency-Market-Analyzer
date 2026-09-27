-- Synthetic data for `dbt build --target ci` (run after init-db.sql and the analytics migration).
-- 180 minutes of BTC and ETH candles: exchange candles for all of them, pipeline candles for
-- minutes 60-179. Both markets alternate 100 / 100.01 and jump to 101 at minute 120 (one HIGH
-- spike each); ETH's pipeline close is off by 1% at minute 90 (one reconciliation mismatch);
-- Flink alerted on the BTC spike (one flink_alert match).

CREATE TEMP TABLE fx AS
SELECT c.id AS crypto_id, c.symbol, g AS i,
       date_trunc('hour', now()) - INTERVAL '4 hours' + g * INTERVAL '1 minute' AS bucket,
       CASE WHEN g >= 120 THEN 101 ELSE 100 + (g % 2) * 0.01 END::numeric AS px
FROM cryptocurrencies c, generate_series(0, 179) g
WHERE c.symbol IN ('BTC', 'ETH');

INSERT INTO coinbase_candles_1m (crypto_id, bucket, open, high, low, close, volume)
SELECT crypto_id, bucket, px, px, px, px, 1 FROM fx;

INSERT INTO price_aggregates_1m (crypto_id, window_start, window_end, open_price, high_price, low_price,
                                 close_price, vwap, volume, quote_volume, trade_count)
SELECT crypto_id, bucket, bucket + INTERVAL '1 minute', p, p, p, p, p, 1, p, 10
FROM (SELECT *, CASE WHEN symbol = 'ETH' AND i = 90 THEN px * 1.01 ELSE px END AS p FROM fx) t
WHERE i >= 60;

INSERT INTO price_alerts (crypto_id, alert_type, severity, z_score, price_change_pct, old_price, new_price,
                          window_start, window_end)
SELECT crypto_id, 'PRICE_SPIKE', 'HIGH', 98, 0.99, 100.01, 101, bucket, bucket + INTERVAL '1 minute'
FROM fx WHERE symbol = 'BTC' AND i = 120;

\echo 'analytics_fixture: loaded'
