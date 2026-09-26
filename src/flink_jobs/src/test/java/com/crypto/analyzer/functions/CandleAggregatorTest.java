package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Candle;
import com.crypto.analyzer.models.Trade;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;

import static org.junit.jupiter.api.Assertions.assertEquals;

class CandleAggregatorTest {

    private static final Instant T0 = Instant.parse("2026-01-01T00:00:00Z");
    private final CandleAggregator agg = new CandleAggregator();

    private static Trade trade(long id, String price, String size, long offsetMs) {
        Instant t = T0.plusMillis(offsetMs);
        return new Trade(id, "BTC", new BigDecimal(price), new BigDecimal(size), "buy", id * 10, t, t.plusMillis(50));
    }

    private CandleAggregator.Accumulator accumulate(Trade... trades) {
        CandleAggregator.Accumulator acc = agg.createAccumulator();
        for (Trade t : trades) {
            acc = agg.add(t, acc);
        }
        return acc;
    }

    private static void assertSameValue(String expected, BigDecimal actual) {
        assertEquals(0, new BigDecimal(expected).compareTo(actual), "expected " + expected + " but was " + actual);
    }

    @Test
    void openAndCloseFollowEventTimeNotArrivalOrder() {
        Candle c = agg.getResult(accumulate(
                trade(2, "101", "1", 2000),
                trade(3, "103", "1", 3000),
                trade(1, "100", "1", 1000)));
        assertSameValue("100", c.open);
        assertSameValue("103", c.close);
        assertSameValue("103", c.high);
        assertSameValue("100", c.low);
        assertEquals(3, c.tradeCount);
        assertEquals("BTC", c.symbol);
    }

    @Test
    void sameTimestampTiesBreakOnTradeId() {
        Candle c = agg.getResult(accumulate(trade(8, "50", "1", 1000), trade(7, "49", "1", 1000)));
        assertSameValue("49", c.open);
        assertSameValue("50", c.close);
    }

    @Test
    void vwapIsQuoteVolumeOverVolume() {
        // 100*1 + 110*3 = 430 quote over 4 base -> vwap 107.5
        Candle c = agg.getResult(accumulate(trade(1, "100", "1", 0), trade(2, "110", "3", 10)));
        assertSameValue("4", c.volume);
        assertSameValue("430", c.quoteVolume);
        assertSameValue("107.5", c.vwap);
    }

    @Test
    void mergeMatchesSinglePassAggregation() {
        Trade[] all = {
                trade(1, "100", "1", 1000), trade(2, "98", "2", 2000), trade(3, "105", "1", 3000),
                trade(4, "101", "4", 4000), trade(5, "99", "1", 5000)};
        Candle single = agg.getResult(accumulate(all));
        Candle merged = agg.getResult(agg.merge(
                accumulate(all[0], all[3]),
                accumulate(all[1], all[2], all[4])));
        assertSameValue(single.open.toPlainString(), merged.open);
        assertSameValue(single.high.toPlainString(), merged.high);
        assertSameValue(single.low.toPlainString(), merged.low);
        assertSameValue(single.close.toPlainString(), merged.close);
        assertSameValue(single.volume.toPlainString(), merged.volume);
        assertSameValue(single.vwap.toPlainString(), merged.vwap);
        assertEquals(single.tradeCount, merged.tradeCount);
    }

    @Test
    void mergeWithEmptyAccumulatorKeepsTheOtherSide() {
        CandleAggregator.Accumulator filled = accumulate(trade(1, "100", "1", 0));
        Candle c = agg.getResult(agg.merge(agg.createAccumulator(), filled));
        assertSameValue("100", c.open);
        assertEquals(1, c.tradeCount);
    }
}
