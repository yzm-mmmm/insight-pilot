/**
 * Markdown 报告渲染组件
 * 把后端生成的分析报告渲染成富文本。图表已在消息气泡的「可视化图表」区块统一展示，
 * 这里只把报告中的 chart://<id> 占位符替换为对应的图表标题引用，避免重复渲染图表。
 */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChartSpec } from "../types/agent";

export function MarkdownReport({
  markdown,
  charts,
}: {
  markdown: string;
  charts: ChartSpec[];
}) {
  const chartById = new Map(charts.map((chart) => [chart.id, chart]));

  return (
    <div className="mt-4 border border-black/10 bg-white/60 px-5 py-4">
      <div className="report-markdown text-[15px] leading-7 text-ink/85">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            img: ({ src, alt }) => {
              if (src && src.startsWith("chart://")) {
                const chart = chartById.get(src.replace("chart://", ""));
                const label = chart?.title || alt || "图表";
                return (
                  <span className="my-1 inline-flex items-center gap-1 rounded bg-moss/10 px-2 py-0.5 text-xs font-medium text-moss">
                    📊 {label}
                  </span>
                );
              }
              return <img src={src} alt={alt ?? ""} className="my-3 max-w-full" />;
            },
          }}
        >
          {markdown}
        </ReactMarkdown>
      </div>
    </div>
  );
}
