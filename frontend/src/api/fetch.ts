import {
  clearAuthSession,
  getAccessToken,
  getRefreshToken,
  updateAuthTokens,
} from "@/lib/authStorage";

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;
  if (!refreshPromise) {
    refreshPromise = fetch(
      `${process.env.NEXT_PUBLIC_API_URL || "/api/v1"}/auth/refresh`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      },
    )
      .then(async (response) => {
        if (!response.ok) return null;
        const payload = await response.json();
        if (!payload.access_token) return null;
        updateAuthTokens(payload.access_token, payload.refresh_token);
        return String(payload.access_token);
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function redirectToLogin() {
  if (typeof window === "undefined") return;
  clearAuthSession();

  if (window.location.pathname.startsWith("/auth/")) return;
  const returnTo = `${window.location.pathname}${window.location.search}`;
  window.location.replace(`/auth/login?returnTo=${encodeURIComponent(returnTo)}`);
}

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (typeof window !== "undefined") {
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(input, { ...init, headers });
  } catch (reason) {
    if (reason instanceof DOMException && reason.name === "AbortError") throw reason;
    throw new ApiError("无法连接服务器，请检查网络后重试", 0, reason);
  }
  if (response.status === 401 && !String(input).includes("/auth/")) {
    const renewedToken = await refreshAccessToken();
    if (renewedToken) {
      headers.set("Authorization", `Bearer ${renewedToken}`);
      try {
        response = await fetch(input, { ...init, headers });
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === "AbortError") throw reason;
        throw new ApiError("无法连接服务器，请检查网络后重试", 0, reason);
      }
    }
  }
  if (response.status === 401) redirectToLogin();
  return response;
}

export async function apiJson<T>(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<T> {
  const response = await apiFetch(input, init);
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail?: unknown }).detail || "")
        : "";
    throw new ApiError(
      detail || `请求失败（HTTP ${response.status}）`,
      response.status,
      payload,
    );
  }
  return payload as T;
}

export function resolveApiUrl(path: string, apiBase = "/api/v1") {
  if (/^https?:\/\//i.test(path)) return path;
  if (path.startsWith("/api/")) return path;
  return `${apiBase.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}
