module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: "#0b1220", surface: "#111b2e", border: "#1e3a5f" },
        accent: { cyan: "#22d3ee", teal: "#2dd4bf" },
      },
    },
  },
  plugins: [],
};
