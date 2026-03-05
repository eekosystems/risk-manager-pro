import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#F0F9FA",
          100: "#D9EFF2",
          200: "#B3DFE5",
          300: "#8DD4DC",
          400: "#5FBAC6",
          500: "#4A9BA5",
          600: "#3D8089",
          700: "#316670",
          800: "#264D54",
          900: "#1A3439",
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"],
      },
      animation: {
        "slide-in": "slideIn 0.3s ease-out",
        shimmer: "shimmer 2s infinite linear",
        "typing-dot": "typingDot 1.2s infinite",
      },
      keyframes: {
        slideIn: {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        typingDot: {
          "0%, 60%, 100%": { transform: "translateY(0)" },
          "30%": { transform: "translateY(-4px)" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
