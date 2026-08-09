import axios from "axios";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

const client = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  headers: { "Content-Type": "application/json" },
});

// JWT 拦截器
client.interceptors.request.use((config) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (typeof window !== "undefined" && error?.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("user");
      if (!window.location.pathname.startsWith("/auth/")) {
        const returnTo = `${window.location.pathname}${window.location.search}`;
        window.location.replace(`/auth/login?returnTo=${encodeURIComponent(returnTo)}`);
      }
    }
    return Promise.reject(error);
  },
);

export default client;
