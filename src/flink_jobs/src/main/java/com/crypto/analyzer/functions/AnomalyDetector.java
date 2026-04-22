package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.OHLCCandle;
import com.crypto.analyzer.models.PriceAlert;
import org.apache.flink.api.common.state.StateTtlConfig;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.time.Time;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.util.Collector;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * Detects price anomalies (±5% intra-window change) and emits {@link PriceAlert} events.
 *
 * <p>State TTL of 1 hour is applied to {@code lastAlertedWindow} so that RocksDB does not
 * accumulate unbounded state for symbols that stop producing data. The TTL is reset on every
 * write so an active symbol is never evicted prematurely.
 */
public class AnomalyDetector extends KeyedProcessFunction<String, OHLCCandle, PriceAlert> {

    private static final long serialVersionUID = 1L;
    private static final Logger LOG = LoggerFactory.getLogger(AnomalyDetector.class);

    private static final BigDecimal SPIKE_THRESHOLD = new BigDecimal("5.0");

    private transient ValueState<Long> lastAlertedWindow;

    @Override
    public void open(Configuration parameters) throws Exception {
        super.open(parameters);

        // TTL prevents unbounded RocksDB growth for keys that go idle.
        StateTtlConfig ttlConfig = StateTtlConfig
                .newBuilder(Time.hours(1))
                .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)
                .setStateVisibility(StateTtlConfig.StateVisibility.NeverReturnExpired)
                .build();

        ValueStateDescriptor<Long> descriptor = new ValueStateDescriptor<>(
                "last-alerted-window", Long.class);
        descriptor.enableTimeToLive(ttlConfig);
        lastAlertedWindow = getRuntimeContext().getState(descriptor);
    }

    @Override
    public void processElement(
            OHLCCandle candle,
            Context ctx,
            Collector<PriceAlert> out) throws Exception {

        try {
            if (candle.getOpen() == null || candle.getClose() == null) {
                LOG.warn("Skipping candle with null prices: {}", candle.getSymbol());
                return;
            }

            if (candle.getOpen().compareTo(BigDecimal.ZERO) == 0) {
                LOG.warn("Skipping candle with zero open price: {}", candle.getSymbol());
                return;
            }

            long windowStart = candle.getWindowStart() != null
                    ? candle.getWindowStart().toEpochMilli()
                    : 0L;

            Long lastWindow = lastAlertedWindow.value();
            if (lastWindow != null && lastWindow.equals(windowStart)) {
                LOG.debug("Skipping duplicate alert for window: {}", windowStart);
                return;
            }

            // ((close - open) / open) * 100
            BigDecimal priceChangePercent = candle.getClose()
                    .subtract(candle.getOpen())
                    .divide(candle.getOpen(), 4, RoundingMode.HALF_EVEN)
                    .multiply(new BigDecimal("100"));

            if (priceChangePercent.abs().compareTo(SPIKE_THRESHOLD) > 0) {
                String alertType = priceChangePercent.compareTo(BigDecimal.ZERO) > 0
                        ? "PRICE_SPIKE"
                        : "PRICE_DROP";

                out.collect(new PriceAlert(
                        candle.getSymbol(),
                        alertType,
                        priceChangePercent,
                        candle.getOpen(),
                        candle.getClose(),
                        candle.getWindowStart(),
                        candle.getWindowEnd()
                ));

                lastAlertedWindow.update(windowStart);

                LOG.info("ANOMALY: {} {} {}% (open={} close={})",
                        candle.getSymbol(), alertType, priceChangePercent,
                        candle.getOpen(), candle.getClose());
            }

        } catch (Exception e) {
            LOG.error("Error in anomaly detection for {}: {}", candle.getSymbol(), e.getMessage(), e);
        }
    }
}
