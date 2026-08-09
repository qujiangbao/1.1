const AUTH_KEYS = ["token", "refresh_token", "user"] as const;

function migrateLegacyStorage() {
  if (typeof window === "undefined") return;
  for (const key of AUTH_KEYS) {
    const legacyValue = window.localStorage.getItem(key);
    if (!window.sessionStorage.getItem(key) && legacyValue) {
      window.sessionStorage.setItem(key, legacyValue);
    }
    window.localStorage.removeItem(key);
  }
}

export function getAccessToken() {
  if (typeof window === "undefined") return null;
  migrateLegacyStorage();
  return window.sessionStorage.getItem("token");
}

export function getRefreshToken() {
  if (typeof window === "undefined") return null;
  migrateLegacyStorage();
  return window.sessionStorage.getItem("refresh_token");
}

export function getStoredUser() {
  if (typeof window === "undefined") return null;
  migrateLegacyStorage();
  return window.sessionStorage.getItem("user");
}

export function setStoredUser(user: unknown) {
  window.sessionStorage.setItem("user", JSON.stringify(user));
}

export function saveAuthSession(
  accessToken: string,
  refreshToken?: string,
  user?: unknown,
) {
  migrateLegacyStorage();
  window.sessionStorage.setItem("token", accessToken);
  if (refreshToken) window.sessionStorage.setItem("refresh_token", refreshToken);
  if (user) setStoredUser(user);
}

export function updateAuthTokens(accessToken: string, refreshToken?: string) {
  window.sessionStorage.setItem("token", accessToken);
  if (refreshToken) window.sessionStorage.setItem("refresh_token", refreshToken);
}

export function clearAuthSession() {
  if (typeof window === "undefined") return;
  for (const key of AUTH_KEYS) {
    window.sessionStorage.removeItem(key);
    window.localStorage.removeItem(key);
  }
}
