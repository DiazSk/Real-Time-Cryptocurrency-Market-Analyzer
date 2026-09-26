package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Trade;
import org.apache.flink.api.common.typeinfo.Types;
import org.apache.flink.streaming.api.operators.KeyedProcessOperator;
import org.apache.flink.streaming.util.KeyedOneInputStreamOperatorTestHarness;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.assertEquals;

class DedupByTradeIdTest {

    private KeyedOneInputStreamOperatorTestHarness<String, Trade, Trade> harness;

    @BeforeEach
    void setUp() throws Exception {
        harness = new KeyedOneInputStreamOperatorTestHarness<>(
                new KeyedProcessOperator<>(new DedupByTradeId()), Trade::getSymbol, Types.STRING);
        harness.open();
    }

    @AfterEach
    void tearDown() throws Exception {
        harness.close();
    }

    private static Trade trade(String symbol, long id) {
        Instant t = Instant.parse("2026-01-01T00:00:00Z").plusSeconds(id);
        return new Trade(id, symbol, BigDecimal.TEN, BigDecimal.ONE, "buy", id, t, t);
    }

    @Test
    void dropsRepeatsAndOlderIdsPerSymbol() throws Exception {
        harness.processElement(trade("BTC", 1), 0);
        harness.processElement(trade("BTC", 2), 0);
        harness.processElement(trade("BTC", 2), 0);   // Kafka retry duplicate
        harness.processElement(trade("BTC", 1), 0);   // older than last seen
        harness.processElement(trade("ETH", 1), 0);   // other symbol has its own state
        harness.processElement(trade("BTC", 3), 0);

        List<String> out = harness.extractOutputValues().stream()
                .map(t -> t.symbol + ":" + t.tradeId)
                .collect(Collectors.toList());
        assertEquals(List.of("BTC:1", "BTC:2", "ETH:1", "BTC:3"), out);
    }
}
