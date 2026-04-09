"use client";

import React, { useEffect, useRef } from "react";
import { useSSE } from "../contexts/SSEContext";

function fmt(n: number) {
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function MainChart({ ticker }: { ticker: string | null }) {
  const { prices, firstPrices, priceHistory } = useSSE();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<unknown>(null);
  const seriesRef = useRef<unknown>(null);

  const price = ticker ? prices[ticker]?.price : null;
  const first = ticker ? firstPrices[ticker]?.price : null;
  const sessionChange = price !== null && price !== undefined && first ? ((price - first) / first) * 100 : null;
  const isUp = sessionChange !== null && sessionChange >= 0;

  // Initialize chart
  useEffect(() => {
    if (typeof window === "undefined" || !containerRef.current) return;

    import("lightweight-charts").then(({ createChart, AreaSeries }) => {
      if (!containerRef.current) return;
      if (chartRef.current) {
        (chartRef.current as { remove: () => void }).remove();
      }

      const chart = createChart(containerRef.current, {
        layout: {
          background: { color: "#0d1117" },
          textColor: "#8b949e",
        },
        grid: {
          vertLines: { color: "#1c2128" },
          horzLines: { color: "#1c2128" },
        },
        crosshair: {
          vertLine: { color: "#30363d" },
          horzLine: { color: "#30363d" },
        },
        rightPriceScale: {
          borderColor: "#30363d",
        },
        timeScale: {
          borderColor: "#30363d",
          timeVisible: true,
          secondsVisible: false,
        },
        handleScroll: true,
        handleScale: true,
      });

      const color = "#209dd7";
      const series = chart.addSeries(AreaSeries, {
        lineColor: color,
        topColor: `${color}30`,
        bottomColor: `${color}00`,
        lineWidth: 2,
        priceLineVisible: true,
        lastValueVisible: true,
        crosshairMarkerVisible: true,
      });

      chartRef.current = chart;
      seriesRef.current = series;

      // Handle resize
      const ro = new ResizeObserver(() => {
        if (containerRef.current && chartRef.current) {
          const { width, height } = containerRef.current.getBoundingClientRect();
          (chartRef.current as { resize: (w: number, h: number) => void }).resize(width, height);
        }
      });
      ro.observe(containerRef.current);

      return () => ro.disconnect();
    });

    return () => {
      if (chartRef.current) {
        (chartRef.current as { remove: () => void }).remove();
        chartRef.current = null;
        seriesRef.current = null;
      }
    };
  }, []);

  // Update data when ticker changes
  useEffect(() => {
    if (!seriesRef.current || !ticker) return;
    const history = priceHistory[ticker] || [];
    if (history.length < 2) return;

    const seen = new Set<number>();
    const deduped = history.filter((d) => {
      if (seen.has(d.time)) return false;
      seen.add(d.time);
      return true;
    });
    (seriesRef.current as { setData: (d: unknown) => void }).setData(deduped);
    (chartRef.current as { timeScale: () => { fitContent: () => void } })?.timeScale().fitContent();
  }, [ticker, priceHistory]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Chart header */}
      <div
        style={{
          padding: "8px 14px",
          display: "flex",
          alignItems: "center",
          gap: 12,
          borderBottom: "1px solid #30363d",
          flexShrink: 0,
        }}
      >
        {ticker ? (
          <>
            <span style={{ fontSize: 16, fontWeight: 700, color: "#e6edf3" }}>{ticker}</span>
            {price !== null && price !== undefined && (
              <>
                <span style={{ fontSize: 18, fontWeight: 600, color: "#e6edf3" }}>
                  ${fmt(price)}
                </span>
                {sessionChange !== null && (
                  <span
                    style={{
                      fontSize: 12,
                      color: isUp ? "#3fb950" : "#f85149",
                      padding: "2px 6px",
                      borderRadius: 3,
                      backgroundColor: isUp ? "rgba(63,185,80,0.12)" : "rgba(248,81,73,0.12)",
                    }}
                  >
                    {isUp ? "+" : ""}
                    {sessionChange.toFixed(2)}%
                  </span>
                )}
              </>
            )}
          </>
        ) : (
          <span style={{ fontSize: 13, color: "#484f58" }}>Select a ticker from the watchlist</span>
        )}
      </div>

      {/* Chart canvas */}
      <div
        ref={containerRef}
        style={{ flex: 1, minHeight: 0 }}
      />
    </div>
  );
}
