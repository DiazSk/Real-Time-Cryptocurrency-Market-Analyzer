package com.crypto.analyzer.models;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.io.Serializable;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;

/**
 * An anomaly alert: a 1-minute log return whose z-score against the symbol's recent
 * history exceeded the detector threshold. Written to price_alerts and to Kafka crypto-alerts.
 */
public class PriceAlert implements Serializable {

    private static final long serialVersionUID = 2L;
    private static final BigDecimal HUNDRED = new BigDecimal("100");

    @JsonProperty("symbol")               public String symbol;
    @JsonProperty("alert_type")           public String alertType;   // PRICE_SPIKE | PRICE_DROP
    @JsonProperty("severity")             public String severity;    // LOW | MEDIUM | HIGH
    @JsonProperty("z_score")              public double zScore;
    @JsonProperty("price_change_percent") public BigDecimal priceChangePercent;
    @JsonProperty("old_price")            public BigDecimal oldPrice;   // previous candle close
    @JsonProperty("new_price")            public BigDecimal newPrice;   // this candle close
    @JsonProperty("window_start")         public String windowStart;
    @JsonProperty("window_end")           public String windowEnd;
    @JsonProperty("timestamp")            public String timestamp;

    public PriceAlert() {}

    /**
     * Build an alert for a candle whose return scored z against the history.
     * Direction (PRICE_SPIKE vs PRICE_DROP) follows the price move itself (close vs prevClose),
     * not the sign of z: in a trending history the EWMA mean can be nonzero, so a positive
     * return can still score a negative z (and vice versa). Severity follows |z|.
     */
    public static PriceAlert fromZScore(Candle candle, BigDecimal prevClose, double z) {
        PriceAlert a = new PriceAlert();
        a.symbol = candle.symbol;
        a.alertType = candle.close.compareTo(prevClose) > 0 ? "PRICE_SPIKE" : "PRICE_DROP";
        a.severity = severityFor(Math.abs(z));
        a.zScore = z;
        a.oldPrice = prevClose;
        a.newPrice = candle.close;
        a.priceChangePercent = candle.close.subtract(prevClose)
                .divide(prevClose, 8, RoundingMode.HALF_EVEN)
                .multiply(HUNDRED)
                .setScale(4, RoundingMode.HALF_EVEN);
        a.windowStart = candle.windowStart.toString();
        a.windowEnd = candle.windowEnd.toString();
        a.timestamp = Instant.now().toString();
        return a;
    }

    public static String severityFor(double absZ) {
        if (absZ >= 8) {
            return "HIGH";
        }
        return absZ >= 6 ? "MEDIUM" : "LOW";
    }

    @Override
    public String toString() {
        return String.format("ALERT [%s] %s %s z=%.2f change=%s%% %s -> %s @ %s",
                severity, symbol, alertType, zScore, priceChangePercent, oldPrice, newPrice, windowStart);
    }
}
