"use client";

import {
  useState,
  useEffect,
  useMemo,
  createContext,
  useContext,
  useCallback,
} from "react";
import {
  clearAuthSession,
  getAccessToken,
  getStoredUser,
  setStoredUser,
} from "@/lib/authStorage";

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
    clearAuthSession();
    setUserState(null);
    setAuthenticated(false);
  }, []);

  const setUser = useCallback((nextUser: UserInfo | null) => {
    setUserState(nextUser);
    setAuthenticated(Boolean(nextUser && getAccessToken()));
  }, []);

  useEffect(() => {
    const token = getAccessToken();
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
        setStoredUser(restored);
        setUserState(restored);
        setAuthenticated(true);
      } catch {
        const stored = getStoredUser();
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

  const canAccess = useCallback(
    (roles: string[]) => Boolean(user && roles.includes(user.role)),
    [user],
  );
  const value = useMemo(
    () => ({ user, setUser, canAccess, authenticated, ready, clearSession }),
    [user, setUser, canAccess, authenticated, ready, clearSession],
  );

  return (
    <UserContext.Provider
      value={value}
    >
      {children}
    </UserContext.Provider>
  );
}

export function useUserContext() {
  return useContext(UserContext);
}
