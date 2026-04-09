"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { WatchlistEntry } from "../types";

interface WatchlistContextValue {
  watchlist: WatchlistEntry[];
  tickers: string[];
  loading: boolean;
  addTicker: (ticker: string) => Promise<{ success: boolean; error?: string }>;
  removeTicker: (ticker: string) => Promise<void>;
  refreshWatchlist: () => Promise<void>;
}

const WatchlistContext = createContext<WatchlistContextValue>({
  watchlist: [],
  tickers: [],
  loading: true,
  addTicker: async () => ({ success: false }),
  removeTicker: async () => {},
  refreshWatchlist: async () => {},
});

export function WatchlistProvider({ children }: { children: React.ReactNode }) {
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const refreshWatchlist = useCallback(async () => {
    try {
      const res = await fetch("/api/watchlist");
      if (res.ok) {
        const data = await res.json();
        setWatchlist(data.tickers || []);
      }
    } catch {
      // Keep stale data
    } finally {
      setLoading(false);
    }
  }, []);

  const addTicker = useCallback(
    async (ticker: string): Promise<{ success: boolean; error?: string }> => {
      try {
        const res = await fetch("/api/watchlist", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticker: ticker.toUpperCase() }),
        });
        const data = await res.json();
        if (res.ok) {
          await refreshWatchlist();
          return { success: true };
        }
        return { success: false, error: data.error?.message || "Failed to add ticker" };
      } catch {
        return { success: false, error: "Network error" };
      }
    },
    [refreshWatchlist]
  );

  const removeTicker = useCallback(
    async (ticker: string) => {
      try {
        await fetch(`/api/watchlist/${ticker}`, { method: "DELETE" });
        await refreshWatchlist();
      } catch {
        // Ignore
      }
    },
    [refreshWatchlist]
  );

  useEffect(() => {
    refreshWatchlist();
  }, [refreshWatchlist]);

  const tickers = watchlist.map((e) => e.ticker);

  return (
    <WatchlistContext.Provider
      value={{ watchlist, tickers, loading, addTicker, removeTicker, refreshWatchlist }}
    >
      {children}
    </WatchlistContext.Provider>
  );
}

export function useWatchlist() {
  return useContext(WatchlistContext);
}
