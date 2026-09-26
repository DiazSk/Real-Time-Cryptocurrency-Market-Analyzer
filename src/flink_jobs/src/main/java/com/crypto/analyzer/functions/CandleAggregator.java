package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Candle;
import com.crypto.analyzer.models.Trade;
import org.apache.flink.api.common.functions.AggregateFunction;

import java.io.Serializable;
import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * Builds an OHLCV candle from trades.
 *
 * <p>Open and close are the trades with the earliest and latest (event_time, trade_id), so
 * out-of-order arrival inside a window does not change the candle.
 */
public class CandleAggregator implements AggregateFunction<Trade, CandleAggregator.Accumulator, Candle> {

    private static final long serialVersionUID = 1L;

    public static class Accumulator implements Serializable {
        private static final long serialVersionUID = 1L;
        public String symbol;
        public BigDecimal open;
        public BigDecimal high;
        public BigDecimal low;
        public BigDecimal close;
        public long openTime = Long.MAX_VALUE;
        public long openTradeId = Long.MAX_VALUE;
        public long closeTime = Long.MIN_VALUE;
        public long closeTradeId = Long.MIN_VALUE;
        public BigDecimal volume = BigDecimal.ZERO;
        public BigDecimal quoteVolume = BigDecimal.ZERO;
        public int tradeCount;
    }

    @Override
    public Accumulator createAccumulator() {
        return new Accumulator();
    }

    @Override
    public Accumulator add(Trade t, Accumulator acc) {
        long ts = t.getEventTimeMillis();
        acc.symbol = t.symbol;
        if (isBefore(ts, t.tradeId, acc.openTime, acc.openTradeId)) {
            acc.open = t.price;
            acc.openTime = ts;
            acc.openTradeId = t.tradeId;
        }
        if (isBefore(acc.closeTime, acc.closeTradeId, ts, t.tradeId)) {
            acc.close = t.price;
            acc.closeTime = ts;
            acc.closeTradeId = t.tradeId;
        }
        acc.high = acc.high == null ? t.price : acc.high.max(t.price);
        acc.low = acc.low == null ? t.price : acc.low.min(t.price);
        acc.volume = acc.volume.add(t.size);
        acc.quoteVolume = acc.quoteVolume.add(t.price.multiply(t.size));
        acc.tradeCount++;
        return acc;
    }

    @Override
    public Candle getResult(Accumulator acc) {
        Candle c = new Candle();
        c.symbol = acc.symbol;
        c.open = acc.open;
        c.high = acc.high;
        c.low = acc.low;
        c.close = acc.close;
        c.volume = acc.volume;
        c.quoteVolume = acc.quoteVolume;
        c.tradeCount = acc.tradeCount;
        c.vwap = acc.volume.signum() > 0
                ? acc.quoteVolume.divide(acc.volume, 8, RoundingMode.HALF_EVEN)
                : acc.close;
        return c;
    }

    @Override
    public Accumulator merge(Accumulator a, Accumulator b) {
        if (b.tradeCount == 0) {
            return a;
        }
        if (a.tradeCount == 0) {
            return b;
        }
        Accumulator m = new Accumulator();
        m.symbol = a.symbol;

        Accumulator first = isBefore(a.openTime, a.openTradeId, b.openTime, b.openTradeId) ? a : b;
        m.open = first.open;
        m.openTime = first.openTime;
        m.openTradeId = first.openTradeId;

        Accumulator last = isBefore(a.closeTime, a.closeTradeId, b.closeTime, b.closeTradeId) ? b : a;
        m.close = last.close;
        m.closeTime = last.closeTime;
        m.closeTradeId = last.closeTradeId;

        m.high = a.high.max(b.high);
        m.low = a.low.min(b.low);
        m.volume = a.volume.add(b.volume);
        m.quoteVolume = a.quoteVolume.add(b.quoteVolume);
        m.tradeCount = a.tradeCount + b.tradeCount;
        return m;
    }

    /** True if (t1, id1) sorts strictly before (t2, id2). */
    static boolean isBefore(long t1, long id1, long t2, long id2) {
        return t1 < t2 || (t1 == t2 && id1 < id2);
    }
}
