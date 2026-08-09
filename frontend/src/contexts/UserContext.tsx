"use client";

import {
  useState,
  useEffect,
  createContext,
  useContext,
  useCallback,
} from "react";

interface UserInfo {
  id: string;
  username: string;
  role: string;
  display_name?: string;
}

interface UserContextType {
  user: UserInfo | null;
  setUser: (user: UserInfo | null) => void;
  canAccess: (roles: string[]) => boolean;
  authenticated: boolean;
  ready: boolean;
  clearSession: () => void;
}

const UserContext = createContext<UserContextType>({
  user: null,
  setUser: () => {},
  canAccess: () => false,
  authenticated: false,
  ready: false,
  clearSession: () => {},
});

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUserState] = useState<UserInfo | null>(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [ready, setReady] = useState(false);

  const clearSession = useCallback(() => {
    localStorage.removeItem("token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user");
    setUserState(null);
    setAuthenticated(false);
  }, []);

  const setUser = useCallback((nextUser: UserInfo | null) => {
    setUserState(nextUser);
    setAuthenticated(Boolean(nextUser && localStorage.getItem("token")));
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setReady(true);
      return;
    }

    const restore = async () => {
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || "/api/v1"}/auth/me`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!response.ok) {
          clearSession();
          return;
        }
        const data = await response.json();
        const restored: UserInfo = {
          id: data.user_id,
          username: data.username,
          role: data.role,
          display_name: data.display_name,
        };
        localStorage.setItem("user", JSON.stringify(restored));
        setUserState(restored);
        setAuthenticated(true);
      } catch {
        const stored = localStorage.getItem("user");
        if (stored) {
          try {
            setUserState(JSON.parse(stored));
            setAuthenticated(true);
          } catch {
            clearSession();
          }
        } else {
          clearSession();
        }
      } finally {
        setReady(true);
      }
    };

    void restore();
  }, [clearSession]);

  const canAccess = (roles: string[]) =>
    Boolean(user && roles.includes(user.role));

  return (
    <UserContext.Provider
      value={{ user, setUser, canAccess, authenticated, ready, clearSession }}
    >
      {children}
    </UserContext.Provider>
  );
}

export function useUserContext() {
  return useContext(UserContext);
}
