/**
 * Tailwind CSS 主题配置
 * 定义前端项目的字体、颜色和阴影扩展（浅绿色清新风）
 */
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '"LXGW WenKai Screen"',
          '"Noto Sans SC"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          "sans-serif",
        ],
        mono: ['"JetBrains Mono"', '"SFMono-Regular"', "Consolas", "monospace"],
      },
      colors: {
        parchment: "#dcfce7",
        surface: "#f4faf6",
        ink: "#1f3d2a",
        soot: "#15803d",
        moss: "#16a34a",
        brass: "#0d9488",
        tomato: "#dc2626",
        mist: "#5c7265",
        "accent-from": "#22c55e",
        "accent-to": "#059669",
      },
      boxShadow: {
        line: "0 1px 0 rgba(22, 101, 52, 0.08)",
        panel: "0 18px 48px rgba(22, 101, 52, 0.12)",
        glow: "0 0 0 1px rgba(22, 163, 74, 0.10), 0 0 28px rgba(22, 163, 74, 0.18)",
      },
    },
  },
  plugins: [],
} satisfies Config;
