import { useSyncExternalStore } from "react";

// Theme handling: the user can pick "light", "dark" or "system" (follow the
// operating system). The choice is saved in localStorage; the theme actually
// in use is written to <html data-theme="light|dark">, and the CSS in
// index.css / styles/auth.css keys its dark palettes off that attribute.
//
// index.html contains a tiny script that does the same thing before the first
// paint, so a dark-mode user never sees a flash of the light theme. Keep the
// storage key ("cc-theme") in sync with that script.

export type ThemePreference = "light" | "dark" | "system";

const STORAGE_KEY = "cc-theme";
const systemDark = window.matchMedia("(prefers-color-scheme: dark)");
const listeners = new Set<() => void>();

function readPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") return stored;
  } catch {
    // Storage can be blocked (private mode); fall through to the default.
  }
  return "system";
}

let preference = readPreference();

function apply() {
  const dark = preference === "dark" || (preference === "system" && systemDark.matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

export function setThemePreference(next: ThemePreference) {
  preference = next;
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // Not saving is fine: the choice still applies until the page is closed.
  }
  apply();
  listeners.forEach((notify) => notify());
}

// Call once at startup (main.tsx). When the OS theme changes while "system"
// is selected, the app follows it live.
export function initTheme() {
  apply();
  systemDark.addEventListener("change", () => {
    if (preference === "system") apply();
  });
}

export function useThemePreference(): [ThemePreference, (next: ThemePreference) => void] {
  const current = useSyncExternalStore(
    (notify) => {
      listeners.add(notify);
      return () => listeners.delete(notify);
    },
    () => preference,
  );
  return [current, setThemePreference];
}
