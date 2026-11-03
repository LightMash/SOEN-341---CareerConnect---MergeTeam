import { useThemePreference } from "../theme";
import type { ThemePreference } from "../theme";
import { MonitorIcon, MoonIcon, SunIcon } from "./icons";

// One button that cycles System -> Light -> Dark. The label and icon show the
// CURRENT choice; the tooltip says what a click does next.
//   variant="nav"      : looks like a sidebar item (label hides when collapsed)
//   variant="floating" : small round button in the corner (login / register)
const ORDER: ThemePreference[] = ["system", "light", "dark"];
const LABELS: Record<ThemePreference, string> = {
  system: "Theme: System",
  light: "Theme: Light",
  dark: "Theme: Dark",
};

interface ThemeToggleProps {
  variant: "nav" | "floating";
}

export default function ThemeToggle({ variant }: ThemeToggleProps) {
  const [preference, setPreference] = useThemePreference();
  const next = ORDER[(ORDER.indexOf(preference) + 1) % ORDER.length];
  const icon =
    preference === "light" ? <SunIcon /> : preference === "dark" ? <MoonIcon /> : <MonitorIcon />;
  const title = `${LABELS[preference]} (click for ${next})`;

  if (variant === "floating") {
    return (
      <button
        type="button"
        className="cc-theme-floating"
        onClick={() => setPreference(next)}
        aria-label={title}
        title={title}
      >
        {icon}
      </button>
    );
  }

  return (
    <button
      type="button"
      className="cc-nav-item cc-theme-nav"
      onClick={() => setPreference(next)}
      aria-label={title}
      title={title}
    >
      <span className="cc-nav-icon">{icon}</span>
      <span className="cc-nav-label">{LABELS[preference]}</span>
    </button>
  );
}
