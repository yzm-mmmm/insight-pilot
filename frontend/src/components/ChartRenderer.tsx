/**
 * ECharts 图表渲染组件
 * 按需引入 echarts 的图表类型、组件和 Canvas 渲染器，把后端下发的图表意图 spec
 * 组装成 ECharts option 后渲染，并在容器尺寸变化时自适应重绘。
 * 统一应用深色配色，使图表与整体深色科技风保持一致。
 */
import { BarChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";
import type { ChartSpec } from "../types/agent";

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
]);

const PALETTE = ["#38bdf8", "#6366f1", "#a78bfa", "#34d399", "#fbbf24", "#f472b6"];

const AXIS_STYLE = {
  axisLine: { lineStyle: { color: "rgba(230,230,240,0.18)" } },
  axisLabel: { color: "#8b8b9e" },
  splitLine: { lineStyle: { color: "rgba(230,230,240,0.07)" } },
};

const TITLE_STYLE = {
  color: "#e6e6f0",
  fontSize: 14,
  fontWeight: 600 as const,
};

const TOOLTIP = {
  backgroundColor: "#1a1a24",
  borderColor: "rgba(230,230,240,0.12)",
  textStyle: { color: "#e6e6f0" },
};

function toNumber(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function buildOption(spec: ChartSpec): echarts.EChartsCoreOption {
  const xField = spec.xField;
  const yFields =
    Array.isArray(spec.yFields) && spec.yFields.length > 0
      ? spec.yFields
      : Array.isArray(spec.series) && spec.series.length > 0
        ? spec.series
        : [];

  // 缺少可用坐标字段时只渲染标题占位，避免 setOption 抛错
  if (!xField || yFields.length === 0) {
    return { title: { text: spec.title, left: "center", textStyle: TITLE_STYLE } };
  }

  const base = { color: PALETTE, textStyle: { color: "#e6e6f0" } };
  const legend = { bottom: 0, textStyle: { color: "#8b8b9e" } };

  if (spec.type === "pie") {
    const valueField = yFields[0];
    return {
      ...base,
      title: { text: spec.title, left: "center", textStyle: TITLE_STYLE },
      tooltip: { trigger: "item", ...TOOLTIP },
      legend,
      series: [
        {
          type: "pie",
          radius: "55%",
          name: spec.title,
          data: spec.rows.map((row) => ({
            name: String(row[xField] ?? ""),
            value: toNumber(row[valueField]),
          })),
        },
      ],
    };
  }

  if (spec.type === "scatter") {
    const valueField = yFields[0];
    return {
      ...base,
      title: { text: spec.title, left: "center", textStyle: TITLE_STYLE },
      tooltip: { trigger: "item", ...TOOLTIP },
      xAxis: { type: "value", name: xField, ...AXIS_STYLE },
      yAxis: { type: "value", name: valueField, ...AXIS_STYLE },
      series: [
        {
          type: "scatter",
          name: spec.title,
          data: spec.rows.map((row) => [toNumber(row[xField]), toNumber(row[valueField])]),
        },
      ],
    };
  }

  // bar / line：x 轴为类目，y 轴为数值，多字段时叠加多条系列
  return {
    ...base,
    title: { text: spec.title, left: "center", textStyle: TITLE_STYLE },
    tooltip: { trigger: "axis", ...TOOLTIP },
    legend: yFields.length > 1 ? legend : undefined,
    grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
    xAxis: {
      type: "category",
      data: spec.rows.map((row) => String(row[xField] ?? "")),
      ...AXIS_STYLE,
    },
    yAxis: { type: "value", ...AXIS_STYLE },
    series: yFields.map((field) => ({
      name: field,
      type: spec.type as "bar" | "line",
      data: spec.rows.map((row) => toNumber(row[field])),
    })),
  };
}

export function ChartRenderer({ spec }: { spec: ChartSpec }) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = echarts.init(containerRef.current);
    chart.setOption(buildOption(spec));

    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [spec]);

  return (
    <div
      ref={containerRef}
      className="mt-4 h-72 w-full border border-white/10 bg-white/[0.02]"
      role="img"
      aria-label={spec.title}
    />
  );
}
