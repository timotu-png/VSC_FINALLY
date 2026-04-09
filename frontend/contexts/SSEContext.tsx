"use client";

import React, { createContext, useContext, useEffect, useRef, useState } from "react";

interface PriceMap {
  [ticker: string]: { price: number; timestamp: number };
}

interface SSEContextValue {
  prices: PriceMap;
  firstPrices: PriceMap;
  connectionStatus: number; // EventSource.readyState: 0=CONNECTING, 1=OPEN, 2=CLOSED
  priceHistory: { [ticker: string]: { time: number; value: number }[] };
}

const SSEContext = createContext<SSEContextValue>({
  prices: {},
  firstPrices: {},
  connectionStatus: 0,
  priceHistory: {},
});

export function SSEProvider({ children }: { children: React.ReactNode }) {
  const [prices, setPrices] = useState<PriceMap>({});
  const [firstPrices, setFirstPrices] = useState<PriceMap>({});
  const [connectionStatus, setConnectionStatus] = useState<number>(0);
  const [priceHistory, setPriceHistory] = useState<{
    [ticker: string]: { time: number; value: number }[];
  }>({});

  const esRef = useRef<EventSource | null>(null);
  const statusIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const es = new EventSource("/api/stream/prices");
    esRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as Record<
          string,
          { ticker: string; price: number; timestamp: number }
        >;

        const now = Date.now() / 1000;

        setPrices((prev) => {
          const next = { ...prev };
          for (const [ticker, update] of Object.entries(data)) {
            next[ticker] = { price: update.price, timestamp: update.timestamp || now };
          }
          return next;
        });

        setFirstPrices((prev) => {
          const next = { ...prev };
          for (const [ticker, update] of Object.entries(data)) {
            if (!next[ticker]) {
              next[ticker] = { price: update.price, timestamp: update.timestamp || now };
            }
          }
          return next;
        });

        setPriceHistory((prev) => {
          const next = { ...prev };
          for (const [ticker, update] of Object.entries(data)) {
            const point = { time: Math.floor(update.timestamp || now), value: update.price };
            const existing = next[ticker] || [];
            // Keep last 500 points per ticker
            const updated = [...existing, point];
            next[ticker] = updated.slice(-500);
          }
          return next;
        });
      } catch {
        // Ignore parse errors
      }
    };

    // Poll readyState every second for connection status indicator
    statusIntervalRef.current = setInterval(() => {
      if (esRef.current) {
        setConnectionStatus(esRef.current.readyState);
      }
    }, 1000);

    return () => {
      es.close();
      if (statusIntervalRef.current) clearInterval(statusIntervalRef.current);
    };
  }, []);

  return (
    <SSEContext.Provider value={{ prices, firstPrices, connectionStatus, priceHistory }}>
      {children}
    </SSEContext.Provider>
  );
}

export function useSSE() {
  return useContext(SSEContext);
}
