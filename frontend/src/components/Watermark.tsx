/**
 * 登录用户水印组件
 * 在页面背景平铺当前登录用户名，作为轻量防泄密水印
 */
function escapeXml(value: string) {
  return value.replace(/[<>&'"]/g, (ch) => {
    const map: Record<string, string> = {
      "<": "&lt;",
      ">": "&gt;",
      "&": "&amp;",
      "'": "&apos;",
      '"': "&quot;",
    };
    return map[ch];
  });
}

export function Watermark({ text }: { text: string }) {
  if (!text) return null;

  const svg =
    `<svg xmlns='http://www.w3.org/2000/svg' width='260' height='180'>` +
    `<text x='50%' y='52%' transform='rotate(-22 130 90)' ` +
    `fill='rgba(230,230,240,0.05)' font-size='15' ` +
    `font-family='system-ui, sans-serif' text-anchor='middle'>${escapeXml(text)}</text>` +
    `</svg>`;

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-10"
      style={{ backgroundImage: `url("data:image/svg+xml,${encodeURIComponent(svg)}")` }}
    />
  );
}
