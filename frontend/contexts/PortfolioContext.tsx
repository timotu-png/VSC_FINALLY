"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { Portfolio, Snapshot } from "../types";

interface TradeResult {
  success: boolean;
  error?: { code: string; message: string };
}

interface PortfolioContextValue {
  portfolio: Portfolio | null;
  history: Snapshot[];
  loading: boolean;
  refreshPortfolio: () => Promise<void>;
  executeTrade: (ticker: string, quantity: number, side: "buy" | "sell") => Promise<TradeResult>;
}

const PortfolioContext = createContext<PortfolioContextValue>({
  portfolio: null,
  history: [],
  loading: true,
  refreshPortfolio: async () => {},
  executeTrade: async () => ({ success: false }),
});

export function PortfolioProvider({ children }: { children: React.ReactNode }) {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [history, setHistory] = useState<Snapshot[]>([]);
  const [loading, setLoading] = useState(true);

  const refreshPortfolio = useCallback(async () => {
    try {
      const [portRes, histRes] = await Promise.all([
        fetch("/api/portfolio"),
        fetch("/api/portfolio/history"),
      ]);
      if (portRes.ok) {
        const data = await portRes.json();
        setPortfolio(data);
      }
      if (histRes.ok) {
        const data = await histRes.json();
        setHistory(data.snapshots || []);
      }
    } catch {
      // Network error — keep stale data
    } finally {
      setLoading(false);
    }
  }, []);

  const executeTrade = useCallback(
    async (ticker: string, quantity: number, side: "buy" | "sell"): Promise<TradeResult> => {
      try {
        const res = await fetch("/api/portfolio/trade", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticker, quantity, side }),
        });
        const data = await res.json();
        if (res.ok) {
          await refreshPortfolio();
          return { success: true };
        }
        return { success: false, error: data.error };
      } catch {
        return { success: false, error: { code: "network_error", message: "Network error" } };
      }
    },
    [refreshPortfolio]
  );

  useEffect(() => {
    refreshPortfolio();
    // Refresh portfolio every 30s
    const interval = setInterval(refreshPortfolio, 30000);
    return () => clearInterval(interval);
  }, [refreshPortfolio]);

  return (
    <PortfolioContext.Provider value={{ portfolio, history, loading, refreshPortfolio, executeTrade }}>
      {children}
    </PortfolioContext.Provider>
  );
}

export function usePortfolio() {
  return useContext(PortfolioContext);
}
