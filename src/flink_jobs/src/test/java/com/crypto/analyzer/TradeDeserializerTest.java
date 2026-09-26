package com.crypto.analyzer;

import com.crypto.analyzer.models.Trade;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

/**
 * A single malformed or tombstone Kafka record must never crash the job: it must deserialize
 * to null so the Kafka source drops it, rather than throwing and crash-looping the checkpoint.
 */
class TradeDeserializerTest {

    private static final String VALID_JSON =
            "{\"trade_id\":1,\"symbol\":\"BTC\",\"price\":\"83982.07\",\"size\":\"0.5\",\"side\":\"buy\","
            + "\"sequence\":10,\"event_time\":\"2026-09-26T04:07:20.310372Z\","
            + "\"ingest_time\":\"2026-09-26T04:07:21.000000Z\"}";

    private CryptoPriceAggregator.TradeDeserializer newDeserializer() throws Exception {
        CryptoPriceAggregator.TradeDeserializer d = new CryptoPriceAggregator.TradeDeserializer();
        d.open(null);
        return d;
    }

    private byte[] bytes(String s) {
        return s.getBytes(StandardCharsets.UTF_8);
    }

    @Test
    void validMessageDeserializes() throws Exception {
        Trade t = newDeserializer().deserialize(bytes(VALID_JSON));
        assertEquals(1L, t.tradeId);
        assertEquals(0, new BigDecimal("83982.07").compareTo(t.price));
    }

    @Test
    void uppercaseSideIsRejected() throws Exception {
        String json = VALID_JSON.replace("\"side\":\"buy\"", "\"side\":\"SELL\"");
        assertNull(newDeserializer().deserialize(bytes(json)));
    }

    @Test
    void missingSideIsRejected() throws Exception {
        String json = "{\"trade_id\":1,\"symbol\":\"BTC\",\"price\":\"83982.07\",\"size\":\"0.5\","
                + "\"sequence\":10,\"event_time\":\"2026-09-26T04:07:20.310372Z\","
                + "\"ingest_time\":\"2026-09-26T04:07:21.000000Z\"}";
        assertNull(newDeserializer().deserialize(bytes(json)));
    }

    @Test
    void jsonNullLiteralReturnsNull() throws Exception {
        assertNull(newDeserializer().deserialize(bytes("null")));
    }

    @Test
    void nullMessageReturnsNull() throws Exception {
        assertNull(newDeserializer().deserialize(null));
    }

    @Test
    void malformedJsonReturnsNull() throws Exception {
        assertNull(newDeserializer().deserialize(bytes("not json")));
    }
}
