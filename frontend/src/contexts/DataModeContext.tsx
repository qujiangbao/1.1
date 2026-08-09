"use client";

import {
  createContext,
  useContext,
  useEffect,
} from "react";

export type DataMode = "real" | "demo";

interface DataModeContextValue {
  mode: DataMode;
  isDemo: boolean;
  ready: boolean;
  setMode: (mode: DataMode) => void;
  resetDemo: () => void;
}

const STORAGE_KEY = "industrial-park-data-mode";
const DataModeContext = createContext<DataModeContextValue | null>(null);
const REAL_DATA_MODE: DataModeContextValue = {
  mode: "real",
  isDemo: false,
  ready: true,
  setMode: () => undefined,
  resetDemo: () => undefined,
};

export function DataModeProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    // 演示沙盘已从实际运营入口移除；清理旧浏览器中残留的 demo 选择。
    window.localStorage.removeItem(STORAGE_KEY);
  }, []);

  return (
    <DataModeContext.Provider value={REAL_DATA_MODE}>
      {children}
    </DataModeContext.Provider>
  );
}

export function useDataMode() {
  const context = useContext(DataModeContext);
  if (!context) {
    throw new Error("useDataMode must be used inside DataModeProvider");
  }
  return context;
}
