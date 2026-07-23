import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        primary: "#1677ff",
        success: "#52c41a",
        warning: "#faad14",
        danger: "#ff4d4f",
      },
    },
  },
  plugins: [],
};

export default config;
