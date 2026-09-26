package com.crypto.analyzer.models;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.Instant;

/**
 * One 1-minute OHLCV candle built from real trades.
 *
 * <p>Public fields keep this a Flink POJO and define the Redis JSON shape read by the API:
 * symbol, windowStart, windowEnd (epoch seconds), open, high, low, close, vwap, volume,
 * quoteVolume, tradeCount.
 */
public class Candle implements Serializable {

    private static final long serialVersionUID = 1L;

    public String symbol;
    public Instant windowStart;
    public Instant windowEnd;
    public BigDecimal open;
    public BigDecimal high;
    public BigDecimal low;
    public BigDecimal close;
    /** Volume-weighted average price: quoteVolume / volume. */
    public BigDecimal vwap;
    /** Base-asset units traded, e.g. BTC. */
    public BigDecimal volume;
    /** Quote currency (USD) traded: sum of price * size. */
    public BigDecimal quoteVolume;
    public int tradeCount;

    public Candle() {}

    public String getSymbol() {
        return symbol;
    }
}
