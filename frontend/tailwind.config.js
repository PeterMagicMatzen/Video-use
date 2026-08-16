module.exports = {
  content: ["./src/**/*.{js,jsx}", "./public/index.html"],
  theme: {
    extend: {
      colors: {
        background: "hsl(240 10% 4%)",
        card: "hsl(240 10% 6%)",
        primary: { DEFAULT: "hsl(65 100% 50%)", foreground: "hsl(0 0% 0%)" },
        accent: { DEFAULT: "hsl(180 100% 50%)", foreground: "hsl(0 0% 0%)" },
        muted: { DEFAULT: "hsl(240 10% 15%)", foreground: "hsl(240 5% 65%)" },
        border: "hsl(240 10% 15%)",
      },
      fontFamily: {
        heading: ["Outfit", "sans-serif"],
        body: ["Inter", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
    },
  },
  plugins: [],
};
