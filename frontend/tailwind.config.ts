/**
 * Tailwind CSS 主题配置
 * 定义前端项目的字体、颜色和阴影扩展（深色科技风）
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
        parchment: "#0a0a0f",
        surface: "#12121a",
        ink: "#f5f6fa",
        soot: "#6366f1",
        moss: "#38bdf8",
        brass: "#a78bfa",
        tomato: "#f87171",
        mist: "#6b6b80",
        "accent-from": "#38bdf8",
        "accent-to": "#6366f1",
      },
      boxShadow: {
        line: "0 1px 0 rgba(255, 255, 255, 0.06)",
        panel: "0 18px 48px rgba(0, 0, 0, 0.45)",
        glow: "0 0 0 1px rgba(255, 255, 255, 0.04), 0 0 28px rgba(99, 102, 241, 0.12)",
      },
    },
  },
  plugins: [],
} satisfies Config;
