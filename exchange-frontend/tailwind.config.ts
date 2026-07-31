import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        card: "var(--card)",
        "card-foreground": "var(--card-foreground)",
        popover: "var(--popover)",
        "popover-foreground": "var(--popover-foreground)",
        primary: "var(--primary)",
        "primary-foreground": "var(--primary-foreground)",
        secondary: "var(--secondary)",
        "secondary-foreground": "var(--secondary-foreground)",
        muted: "var(--muted)",
        "muted-foreground": "var(--muted-foreground)",
        accent: "var(--accent)",
        "accent-foreground": "var(--accent-foreground)",
        destructive: "var(--destructive)",
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        bria: {
          white: "#FFFFFF",
          "light-gray": "#EBECF0",
          "dark-gray": "#9E9E9E",
          black: "#000000",
          purple: "#7D29F2",
          "purple-2": "#9D5FF5",
          "purple-3": "#DDCCF4",
          yellow: "#F2BC1B",
          magenta: "#D70067",
          green: "#5BC29E",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) * 0.8)",
        sm: "calc(var(--radius) * 0.6)",
      },
      fontFamily: {
        heading: ["Space Grotesk", "Arial Black", "sans-serif"],
        body: ["Sora", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
