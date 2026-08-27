"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Theme = "dark" | "light";

const STORAGE_KEY = "hslab-theme";

const ThemeContext = createContext<{ theme: Theme; toggleTheme: () => void } | null>(null);

// Redesign default is dark (see design_handoff_dashboard_redesign) — a stored
// preference overrides it. The <head> inline script in app/layout.tsx applies
// the same default before hydration to avoid a flash of the wrong theme.
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    // Deliberate: localStorage is only readable client-side, so restoring the
    // stored theme has to happen in an effect, not a lazy useState initializer
    // (which would throw during SSR) — same hydration-safe pattern every
    // theme-toggle library uses.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (stored === "light" || stored === "dark") setTheme(stored);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  return (
    <ThemeContext.Provider
      value={{ theme, toggleTheme: () => setTheme((t) => (t === "dark" ? "light" : "dark")) }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
