package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.OHLCCandle;
import com.crypto.analyzer.models.PriceAlert;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.util.Collector;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * Anomaly detector for cryptocurrency price spikes/drops.
 * 
 * Detects:
 * - Price spike: >5% increase in 1-minute window
 * - Price drop: >5% decrease in 1-minute window
 * 
 * Uses keyed state to prevent duplicate alerts when windows re-trigger
 * with late data.
 * 
 * @author Zaid
 */
public class AnomalyDetector extends KeyedProcessFunction<String, OHLCCandle, PriceAlert> {
    
    private static final long serialVersionUID = 1L;
    private static final Logger LOG = LoggerFactory.getLogger(AnomalyDetector.class);
    
    // Anomaly threshold: 5% price change
    private static final BigDecimal SPIKE_THRESHOLD = new BigDecimal("5.0");
    
    // State to track last alerted window (prevents duplicates)
    private transient ValueState<Long> lastAlertedWindow;
    
    @Override
    public void open(Configuration parameters) throws Exception {
        super.open(parameters);
        
        // Initialize state to track last window we alerted for
        ValueStateDescriptor<Long> descriptor = new ValueStateDescriptor<>(
            "last-alerted-window",  // State name
            Long.class              // State type
        );
        lastAlertedWindow = getRuntimeContext().getState(descriptor);
    }
    
    @Override
    public void processElement(
            OHLCCandle candle,
            Context ctx,
            Collector<PriceAlert> out) throws Exception {
        
        try {
            // Validate candle has required data
            if (candle.getOpen() == null || candle.getClose() == null) {
                LOG.warn("Skipping candle with null prices: {}", candle.getSymbol());
                return;
            }
            
            // Skip if open price is zero (division by zero)
            if (candle.getOpen().compareTo(BigDecimal.ZERO) == 0) {
                LOG.warn("Skipping candle with zero open price: {}", candle.getSymbol());
                return;
            }
            
            // Get window start time (unique identifier for this window)
            long windowStart = candle.getWindowStart() != null 
                ? candle.getWindowStart().toEpochMilli() 
                : 0L;
            
            // Check if we already alerted for this window
            Long lastWindow = lastAlertedWindow.value();
            if (lastWindow != null && lastWindow.equals(windowStart)) {
                // Already alerted for this window (late data re-trigger)
                LOG.debug("Skipping duplicate alert for window: {}", windowStart);
                return;
            }
            
            // Calculate price change percentage
            // Formula: ((close - open) / open) * 100
            BigDecimal priceChange = candle.getClose().subtract(candle.getOpen());
            BigDecimal priceChangePercent = priceChange
                    .divide(candle.getOpen(), 4, RoundingMode.HALF_EVEN)
                    .multiply(new BigDecimal("100"));
            
            // Check if absolute change exceeds threshold
            BigDecimal absChange = priceChangePercent.abs();
            
            if (absChange.compareTo(SPIKE_THRESHOLD) > 0) {
                // Determine alert type
                String alertType = priceChangePercent.compareTo(BigDecimal.ZERO) > 0
                        ? "PRICE_SPIKE"
                        : "PRICE_DROP";
                
                // Create alert
                PriceAlert alert = new PriceAlert(
                    candle.getSymbol(),
                    alertType,
                    priceChangePercent,
                    candle.getOpen(),
                    candle.getClose(),
                    candle.getWindowStart(),
                    candle.getWindowEnd()
                );
                
                // Emit alert
                out.collect(alert);
                
                // Update state to prevent duplicate alerts
                lastAlertedWindow.update(windowStart);
                
                LOG.info("⚠️  ANOMALY DETECTED: {} {} by {}% (Open: {} → Close: {})",
                        candle.getSymbol(),
                        alertType,
                        priceChangePercent,
                        candle.getOpen(),
                        candle.getClose());
            }
            
        } catch (Exception e) {
            LOG.error("Error in anomaly detection for {}: {}", 
                    candle.getSymbol(), e.getMessage(), e);
        }
    }
}
