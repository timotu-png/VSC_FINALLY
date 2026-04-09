"use client";

import React, { useEffect, useRef } from "react";
import { usePortfolio } from "../contexts/PortfolioContext";

export default function PLChart() {
  const { history } = usePortfolio();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<unknown>(null);
  const seriesRef = useRef<unknown>(null);

  // Initialize chart once
  useEffect(() => {
    if (typeof window === "undefined" || !containerRef.current) return;

    import("lightweight-charts").then(({ createChart, AreaSeries }) => {
      if (!containerRef.current) return;
      if (chartRef.current) return;

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
        rightPriceScale: { borderColor: "#30363d" },
        timeScale: {
          borderColor: "#30363d",
          timeVisible: true,
        },
        handleScroll: true,
        handleScale: true,
      });

      const series = chart.addSeries(AreaSeries, {
        lineColor: "#ecad0a",
        topColor: "rgba(236,173,10,0.25)",
        bottomColor: "rgba(236,173,10,0.02)",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: true,
      });

      chartRef.current = chart;
      seriesRef.current = series;

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

  // Update data when history changes
  useEffect(() => {
    if (!seriesRef.current || history.length === 0) return;

    const seen = new Set<number>();
    const data = history
      .map((s) => ({
        time: Math.floor(new Date(s.recorded_at).getTime() / 1000) as number,
        value: s.total_value,
      }))
      .filter((d) => {
        if (seen.has(d.time)) return false;
        seen.add(d.time);
        return true;
      });

    (seriesRef.current as { setData: (d: unknown) => void }).setData(data);
    (chartRef.current as { timeScale: () => { fitContent: () => void } })?.timeScale().fitContent();
  }, [history]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <div
        style={{
          padding: "6px 14px",
          borderBottom: "1px solid #30363d",
          fontSize: 10,
          color: "#8b949e",
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          flexShrink: 0,
        }}
      >
        Portfolio Value
      </div>
      <div ref={containerRef} style={{ flex: 1, minHeight: 0 }} />
    </div>
  );
}
