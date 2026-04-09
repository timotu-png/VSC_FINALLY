"use client";

import React, { useEffect, useRef, useState } from "react";
import { useSSE } from "../contexts/SSEContext";
import { useWatchlist } from "../contexts/WatchlistContext";

function fmt(n: number) {
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function Sparkline({
  data,
  width = 100,
  height = 32,
}: {
  data: { time: number; value: number }[];
  width?: number;
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<unknown>(null);
  const seriesRef = useRef<unknown>(null);

  useEffect(() => {
    if (typeof window === "undefined" || !containerRef.current || data.length < 2) return;

    import("lightweight-charts").then(({ createChart, LineSeries }) => {
      if (!containerRef.current) return;
      if (chartRef.current) {
        (chartRef.current as { remove: () => void }).remove();
      }

      const chart = createChart(containerRef.current, {
        width,
        height,
        layout: { background: { color: "transparent" }, textColor: "transparent" },
        grid: { vertLines: { visible: false }, horzLines: { visible: false } },
        crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
        rightPriceScale: { visible: false },
        leftPriceScale: { visible: false },
        timeScale: { visible: false, borderVisible: false },
        handleScroll: false,
        handleScale: false,
      });

      const last = data[data.length - 1];
      const first = data[0];
      const color = last.value >= first.value ? "#3fb950" : "#f85149";

      const series = chart.addSeries(LineSeries, {
        color,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });

      // Deduplicate by time
      const seen = new Set<number>();
      const deduped = data.filter((d) => {
        if (seen.has(d.time)) return false;
        seen.add(d.time);
        return true;
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      series.setData(deduped as any[]);
      chart.timeScale().fitContent();

      chartRef.current = chart;
      seriesRef.current = series;
    });

    return () => {
      if (chartRef.current) {
        (chartRef.current as { remove: () => void }).remove();
        chartRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.length > 1 ? data[0].value : 0, data.length]);

  return <div ref={containerRef} style={{ width, height }} />;
}

function TickerRow({
  ticker,
  selected,
  onSelect,
  onRemove,
}: {
  ticker: string;
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
}) {
  const { prices, firstPrices, priceHistory } = useSSE();
  const [flashClass, setFlashClass] = useState("");
  const prevPriceRef = useRef<number | null>(null);

  const current = prices[ticker];
  const first = firstPrices[ticker];
  const history = priceHistory[ticker] || [];

  const price = current?.price ?? null;
  const sessionChange =
    price !== null && first
      ? ((price - first.price) / first.price) * 100
      : null;
  const isUp = sessionChange !== null && sessionChange > 0;
  const isDown = sessionChange !== null && sessionChange < 0;

  useEffect(() => {
    if (price === null) return;
    if (prevPriceRef.current !== null && prevPriceRef.current !== price) {
      const cls = price > prevPriceRef.current ? "flash-up" : "flash-down";
      setFlashClass(cls);
      const t = setTimeout(() => setFlashClass(""), 650);
      return () => clearTimeout(t);
    }
    prevPriceRef.current = price;
  }, [price]);

  return (
    <div
      className={flashClass}
      onClick={onSelect}
      style={{
        padding: "8px 10px",
        cursor: "pointer",
        borderLeft: selected ? "2px solid #ecad0a" : "2px solid transparent",
        backgroundColor: selected ? "rgba(236,173,10,0.06)" : "transparent",
        borderBottom: "1px solid #1c2128",
        display: "flex",
        flexDirection: "column",
        gap: 4,
        transition: "background-color 0.1s",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: "#e6edf3" }}>{ticker}</span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            style={{
              background: "none",
              border: "none",
              color: "#484f58",
              cursor: "pointer",
              fontSize: 10,
              padding: "0 2px",
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#e6edf3" }}>
            {price !== null ? `$${fmt(price)}` : "—"}
          </div>
          {sessionChange !== null && (
            <div
              style={{
                fontSize: 10,
                color: isUp ? "#3fb950" : isDown ? "#f85149" : "#8b949e",
              }}
            >
              {isUp ? "+" : ""}
              {sessionChange.toFixed(2)}%
            </div>
          )}
        </div>
      </div>
      {history.length > 1 && (
        <Sparkline data={history} width={200} height={30} />
      )}
    </div>
  );
}

export default function WatchlistPanel({
  selectedTicker,
  onSelectTicker,
}: {
  selectedTicker: string | null;
  onSelectTicker: (ticker: string) => void;
}) {
  const { watchlist, addTicker, removeTicker } = useWatchlist();
  const [adding, setAdding] = useState(false);
  const [newTicker, setNewTicker] = useState("");
  const [addError, setAddError] = useState("");

  async function handleAdd() {
    if (!newTicker.trim()) return;
    const result = await addTicker(newTicker.trim().toUpperCase());
    if (result.success) {
      setNewTicker("");
      setAdding(false);
      setAddError("");
    } else {
      setAddError(result.error || "Failed");
    }
  }

  return (
    <div
      style={{
        width: 240,
        flexShrink: 0,
        backgroundColor: "#161b22",
        borderRight: "1px solid #30363d",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "8px 10px",
          borderBottom: "1px solid #30363d",
          fontSize: 10,
          color: "#8b949e",
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          flexShrink: 0,
        }}
      >
        Watchlist
      </div>

      {/* Tickers */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {watchlist.map((entry) => (
          <TickerRow
            key={entry.ticker}
            ticker={entry.ticker}
            selected={selectedTicker === entry.ticker}
            onSelect={() => onSelectTicker(entry.ticker)}
            onRemove={() => removeTicker(entry.ticker)}
          />
        ))}
      </div>

      {/* Add ticker */}
      <div
        style={{
          padding: "8px 10px",
          borderTop: "1px solid #30363d",
          flexShrink: 0,
        }}
      >
        {adding ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={{ display: "flex", gap: 4 }}>
              <input
                autoFocus
                value={newTicker}
                onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleAdd();
                  if (e.key === "Escape") {
                    setAdding(false);
                    setNewTicker("");
                    setAddError("");
                  }
                }}
                placeholder="TICKER"
                style={{
                  flex: 1,
                  background: "#1c2128",
                  border: "1px solid #30363d",
                  color: "#e6edf3",
                  padding: "4px 6px",
                  fontSize: 12,
                  borderRadius: 3,
                  outline: "none",
                }}
              />
              <button
                onClick={handleAdd}
                style={{
                  background: "#209dd7",
                  border: "none",
                  color: "#fff",
                  padding: "4px 8px",
                  fontSize: 11,
                  borderRadius: 3,
                  cursor: "pointer",
                }}
              >
                Add
              </button>
            </div>
            {addError && (
              <div style={{ fontSize: 10, color: "#f85149" }}>{addError}</div>
            )}
          </div>
        ) : (
          <button
            onClick={() => setAdding(true)}
            style={{
              width: "100%",
              background: "none",
              border: "1px dashed #30363d",
              color: "#8b949e",
              padding: "5px",
              fontSize: 11,
              borderRadius: 3,
              cursor: "pointer",
              textAlign: "center",
            }}
          >
            + Add Ticker
          </button>
        )}
      </div>
    </div>
  );
}
