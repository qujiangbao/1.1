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

export default client;
