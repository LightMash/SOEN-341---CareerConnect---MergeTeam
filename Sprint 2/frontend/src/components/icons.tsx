// Small inline SVG icons (no icon library needed). They draw with
// `currentColor`, so they automatically take on the text color of whatever
// button they sit in — the sidebar's hover and active colors just work.

interface IconProps {
  size?: number;
}

// Shared SVG attributes: a 24x24 viewBox with a 2px rounded outline.
// aria-hidden because the icons are decorative — every button that uses one
// also has a text label (or a title/aria-label) for screen readers.
function svgProps(size: number) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
}

export function BriefcaseIcon({ size = 20 }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />
    </svg>
  );
}

export function ClipboardIcon({ size = 20 }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path d="M9 4h6v3H9z" />
      <path d="M9 12h6M9 16h4" />
    </svg>
  );
}

export function UserIcon({ size = 20 }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </svg>
  );
}

export function LogoutIcon({ size = 20 }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

// Points left ("collapse"); CSS rotates it 180° when the sidebar is collapsed
// so it points right ("expand"). One icon, no second asset.
export function ChevronIcon({ size = 18 }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}

export function SunIcon({ size = 20 }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}

export function MoonIcon({ size = 20 }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  );
}

export function MonitorIcon({ size = 20 }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M8 20h8M12 16v4" />
    </svg>
  );
}
