package com.crypto.analyzer.utils;

import java.util.HashMap;
import java.util.Map;

/**
 * Utility class to map cryptocurrency symbols to database IDs.
 *
 * Maps symbols to crypto_id values in the cryptocurrencies table.
 * Keep aligned with configs/init-db.sql seed order and
 * src/api/config.py::SUPPORTED_SYMBOLS.
 */
public class CryptoIdMapper {

    private static final Map<String, Integer> SYMBOL_TO_ID = new HashMap<>();

    static {
        SYMBOL_TO_ID.put("BTC",   1);
        SYMBOL_TO_ID.put("ETH",   2);
        SYMBOL_TO_ID.put("SOL",   3);
        SYMBOL_TO_ID.put("XRP",   4);
        SYMBOL_TO_ID.put("ADA",   5);
        SYMBOL_TO_ID.put("DOGE",  6);
        SYMBOL_TO_ID.put("AVAX",  7);
        SYMBOL_TO_ID.put("MATIC", 8);
    }
    
    /**
     * Get crypto_id for a given symbol
     * 
     * @param symbol Cryptocurrency symbol (BTC, ETH)
     * @return crypto_id or -1 if not found
     */
    public static int getCryptoId(String symbol) {
        return SYMBOL_TO_ID.getOrDefault(symbol, -1);
    }
    
    /**
     * Check if symbol is supported
     */
    public static boolean isSupported(String symbol) {
        return SYMBOL_TO_ID.containsKey(symbol);
    }
    
    /**
     * Get all supported symbols
     */
    public static String[] getSupportedSymbols() {
        return SYMBOL_TO_ID.keySet().toArray(new String[0]);
    }
}
