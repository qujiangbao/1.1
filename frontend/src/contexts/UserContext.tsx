"use client";

import { useState, useEffect, createContext, useContext } from "react";

interface UserInfo {
  id: string;
  username: string;
  role: string;
  display_name?: string;
}

interface UserContextType {
  user: UserInfo | null;
  setUser: (u: UserInfo | null) => void;
  canAccess: (roles: string[]) => boolean;
}

const UserContext = createContext<UserContextType>({
  user: null,
  setUser: () => {},
  canAccess: () => false,
});

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    // 尝试从 localStorage 恢复 user info
    const stored = localStorage.getItem("user");
    if (stored) {
      try {
        setUser(JSON.parse(stored));
      } catch {}
    }
  }, []);

  const canAccess = (roles: string[]) => {
    if (!user) return false;
    return roles.includes(user.role);
  };

  return (
    <UserContext.Provider value={{ user, setUser, canAccess }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUserContext() {
  return useContext(UserContext);
}
