/** Tokens come from CSS variables (src/theme/tokens.css) so the config is portable
 *  across all six portfolio projects unchanged. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        accent: "var(--accent)",
        "accent-2": "var(--accent-2)",
        line: "var(--border)",
        "line-strong": "var(--border-strong)",
        body: "var(--text)",
        dim: "var(--text-2)",
        muted: "var(--text-muted)",
        ok: "var(--success)",
        warn: "var(--warning)",
        bad: "var(--danger)",
      },
      borderRadius: {
        card: "16px",
        panel: "20px",
        input: "10px",
        btn: "12px",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.25)",
      },
    },
  },
  plugins: [],
};
