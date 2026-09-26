package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Candle;
import com.crypto.analyzer.models.PriceAlert;
import org.apache.flink.api.common.typeinfo.Types;
import org.apache.flink.streaming.api.operators.KeyedProcessOperator;
import org.apache.flink.streaming.util.KeyedOneInputStreamOperatorTestHarness;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ZScoreAnomalyDetectorTest {

    private static final Instant T0 = Instant.parse("2026-01-01T00:00:00Z");

    private KeyedOneInputStreamOperatorTestHarness<String, Candle, PriceAlert> harness;
    private BigDecimal lastClose;
    private int minute;

    @BeforeEach
    void setUp() throws Exception {
        harness = new KeyedOneInputStreamOperatorTestHarness<>(
                new KeyedProcessOperator<>(new ZScoreAnomalyDetector()), Candle::getSymbol, Types.STRING);
        harness.open();
        lastClose = new BigDecimal("100");
        minute = 0;
    }

    @AfterEach
    void tearDown() throws Exception {
        harness.close();
    }

    /** Feed the next 1-minute candle, whose close is lastClose * exp(logReturn). */
    private void feed(double logReturn, int trades) throws Exception {
        BigDecimal close = lastClose.multiply(BigDecimal.valueOf(Math.exp(logReturn)))
                .setScale(8, RoundingMode.HALF_EVEN);
        Candle c = new Candle();
        c.symbol = "BTC";
        c.windowStart = T0.plusSeconds(60L * minute);
        c.windowEnd = c.windowStart.plusSeconds(60);
        c.open = lastClose;
        c.high = close.max(lastClose);
        c.low = close.min(lastClose);
        c.close = close;
        c.vwap = close;
        c.volume = BigDecimal.ONE;
        c.quoteVolume = close;
        c.tradeCount = trades;
        harness.processElement(c, c.windowEnd.toEpochMilli() - 1);
        lastClose = close;
        minute++;
    }

    /** One anchoring candle, then n calm returns alternating +/-step. */
    private void warmUp(int n, double step) throws Exception {
        feed(0, 10);
        for (int i = 0; i < n; i++) {
            feed(i % 2 == 0 ? step : -step, 10);
        }
    }

    private List<PriceAlert> alerts() {
        return harness.extractOutputValues();
    }

    @Test
    void noAlertDuringWarmUp() throws Exception {
        warmUp(10, 0.001);
        feed(0.05, 10);
        assertTrue(alerts().isEmpty());
    }

    @Test
    void largeRiseAfterWarmUpIsHighSeveritySpike() throws Exception {
        warmUp(40, 0.001);
        BigDecimal before = lastClose;
        feed(0.05, 10);
        List<PriceAlert> out = alerts();
        assertEquals(1, out.size());
        PriceAlert a = out.get(0);
        assertEquals("PRICE_SPIKE", a.alertType);
        assertEquals("HIGH", a.severity);
        assertTrue(a.zScore > 8, "z was " + a.zScore);
        assertEquals(0, before.compareTo(a.oldPrice));
        assertEquals(0, lastClose.compareTo(a.newPrice));
        assertEquals(T0.plusSeconds(60L * 41).toString(), a.windowStart);
    }

    @Test
    void largeFallIsPriceDrop() throws Exception {
        warmUp(40, 0.001);
        feed(-0.05, 10);
        assertEquals(1, alerts().size());
        assertEquals("PRICE_DROP", alerts().get(0).alertType);
        assertTrue(alerts().get(0).zScore < -8);
    }

    @Test
    void calmMoveDoesNotAlert() throws Exception {
        warmUp(40, 0.001);
        feed(0.001, 10);
        assertTrue(alerts().isEmpty());
    }

    @Test
    void thinCandleIsIgnored() throws Exception {
        warmUp(40, 0.001);
        feed(0.05, 3);
        assertTrue(alerts().isEmpty());
    }

    @Test
    void gapInMinutesReanchorsWithoutScoring() throws Exception {
        warmUp(40, 0.001);
        minute += 5;              // five quiet minutes with no candle
        feed(0.05, 10);
        assertTrue(alerts().isEmpty());
    }

    @Test
    void zScoreIsClampedForNearFlatHistory() throws Exception {
        warmUp(40, 1e-9);
        feed(0.05, 10);
        assertEquals(1, alerts().size());
        assertEquals(ZScoreAnomalyDetector.Z_CLAMP, alerts().get(0).zScore);
    }

    @Test
    void trendingHistoryLabelsDirectionByPriceMoveNotZ() throws Exception {
        // Steady uptrend: EWMA mean converges to ~+0.002 with a small sd, so a positive
        // return well below the mean still scores a large negative z. Direction must follow
        // the price move (r > 0 => PRICE_SPIKE), not the sign of z.
        feed(0, 10);
        for (int i = 0; i < 150; i++) {
            feed(i % 2 == 0 ? 0.0021 : 0.0019, 10);
        }
        BigDecimal before = lastClose;
        feed(0.0001, 10);
        List<PriceAlert> out = alerts();
        assertEquals(1, out.size());
        PriceAlert a = out.get(0);
        assertEquals("PRICE_SPIKE", a.alertType);
        assertTrue(a.zScore < -4, "z was " + a.zScore);
        assertTrue(a.newPrice.compareTo(before) > 0, "newPrice " + a.newPrice + " should exceed oldPrice " + before);
    }

    @Test
    void severityBands() {
        assertEquals("LOW", PriceAlert.severityFor(4.01));
        assertEquals("LOW", PriceAlert.severityFor(5.99));
        assertEquals("MEDIUM", PriceAlert.severityFor(6.0));
        assertEquals("HIGH", PriceAlert.severityFor(8.0));
    }
}
