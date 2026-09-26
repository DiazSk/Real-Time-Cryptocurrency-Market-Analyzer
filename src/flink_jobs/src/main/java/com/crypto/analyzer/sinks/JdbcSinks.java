package com.crypto.analyzer.sinks;

import com.crypto.analyzer.models.Candle;
import com.crypto.analyzer.models.PriceAlert;
import com.crypto.analyzer.models.Trade;
import org.apache.flink.connector.jdbc.JdbcConnectionOptions;
import org.apache.flink.connector.jdbc.JdbcExecutionOptions;
import org.apache.flink.connector.jdbc.JdbcSink;
import org.apache.flink.streaming.api.functions.sink.SinkFunction;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;

/**
 * TimescaleDB sinks.
 *
 * <p>All three are at-least-once: batches flush on checkpoint and can be re-sent after a
 * restart. Idempotent SQL makes the stored result effectively-once: ON CONFLICT DO NOTHING
 * for trades and alerts, an upsert for candles. crypto_id is resolved from the symbol inside
 * the SQL, so there is no Java-side symbol map to keep in sync; unknown symbols insert nothing.
 */
public final class JdbcSinks {

    private JdbcSinks() {}

    private static final String RAW_TRADES_SQL =
            "INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time) "
            + "SELECT id, ?, ?, ?, ?, ?, ?, ? FROM cryptocurrencies WHERE symbol = ? "
            + "ON CONFLICT (crypto_id, trade_id, event_time) DO NOTHING";

    private static final String CANDLES_SQL =
            "INSERT INTO price_aggregates_1m (crypto_id, window_start, window_end, open_price, high_price, "
            + "  low_price, close_price, vwap, volume, quote_volume, trade_count) "
            + "SELECT id, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? FROM cryptocurrencies WHERE symbol = ? "
            + "ON CONFLICT (crypto_id, window_start) DO UPDATE SET "
            + "  window_end = EXCLUDED.window_end, open_price = EXCLUDED.open_price, "
            + "  high_price = EXCLUDED.high_price, low_price = EXCLUDED.low_price, "
            + "  close_price = EXCLUDED.close_price, vwap = EXCLUDED.vwap, volume = EXCLUDED.volume, "
            + "  quote_volume = EXCLUDED.quote_volume, trade_count = EXCLUDED.trade_count, updated_at = now()";

    private static final String ALERTS_SQL =
            "INSERT INTO price_alerts (crypto_id, alert_type, severity, z_score, price_change_pct, "
            + "  old_price, new_price, window_start, window_end) "
            + "SELECT id, ?, ?, ?, ?, ?, ?, ?, ? FROM cryptocurrencies WHERE symbol = ? "
            + "ON CONFLICT (crypto_id, window_start, alert_type) DO NOTHING";

    public static SinkFunction<Trade> rawTrades(JdbcConnectionOptions conn) {
        return JdbcSink.sink(RAW_TRADES_SQL, (ps, t) -> {
            ps.setLong(1, t.tradeId);
            ps.setBigDecimal(2, t.price);
            ps.setBigDecimal(3, t.size);
            ps.setString(4, t.side);
            ps.setLong(5, t.sequence);
            ps.setObject(6, utc(t.eventTime));
            ps.setObject(7, utc(t.ingestTime));
            ps.setString(8, t.symbol);
        }, batching(500, 1000), conn);
    }

    public static SinkFunction<Candle> candles(JdbcConnectionOptions conn) {
        return JdbcSink.sink(CANDLES_SQL, (ps, c) -> {
            ps.setObject(1, utc(c.windowStart));
            ps.setObject(2, utc(c.windowEnd));
            ps.setBigDecimal(3, c.open);
            ps.setBigDecimal(4, c.high);
            ps.setBigDecimal(5, c.low);
            ps.setBigDecimal(6, c.close);
            ps.setBigDecimal(7, c.vwap);
            ps.setBigDecimal(8, c.volume);
            ps.setBigDecimal(9, c.quoteVolume);
            ps.setInt(10, c.tradeCount);
            ps.setString(11, c.symbol);
        }, batching(100, 1000), conn);
    }

    public static SinkFunction<PriceAlert> alerts(JdbcConnectionOptions conn) {
        return JdbcSink.sink(ALERTS_SQL, (ps, a) -> {
            ps.setString(1, a.alertType);
            ps.setString(2, a.severity);
            ps.setBigDecimal(3, BigDecimal.valueOf(a.zScore).setScale(4, RoundingMode.HALF_EVEN));
            ps.setBigDecimal(4, a.priceChangePercent);
            ps.setBigDecimal(5, a.oldPrice);
            ps.setBigDecimal(6, a.newPrice);
            ps.setObject(7, utc(Instant.parse(a.windowStart)));
            ps.setObject(8, utc(Instant.parse(a.windowEnd)));
            ps.setString(9, a.symbol);
        }, batching(1, 1000), conn);
    }

    private static OffsetDateTime utc(Instant instant) {
        return OffsetDateTime.ofInstant(instant, ZoneOffset.UTC);
    }

    private static JdbcExecutionOptions batching(int size, long intervalMs) {
        return JdbcExecutionOptions.builder()
                .withBatchSize(size)
                .withBatchIntervalMs(intervalMs)
                .withMaxRetries(3)
                .build();
    }
}
