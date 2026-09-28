import type { Config } from "tailwindcss";
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: { extend: {
    colors: { paper: "#F2F6F1", sheet: "#FCFDFB", pine: "#12352F", moss: "#4E6B62", mist: "#D9E3DC", cap: "#F0B429", berry: "#A93254" },
    fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"], serif: ["Georgia", "Cambria", "serif"] },
    keyframes: { rise: { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "none" } },
                 dot: { "0%,80%,100%": { opacity: ".25" }, "40%": { opacity: "1" } } },
    animation: { rise: "rise .35s ease-out both", dot: "dot 1.2s infinite" },
  } },
  plugins: [require("@tailwindcss/typography")],
} satisfies Config;
