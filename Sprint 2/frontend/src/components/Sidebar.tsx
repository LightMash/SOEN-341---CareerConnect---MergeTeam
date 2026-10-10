import type { ReactNode } from "react";
import type { User } from "../api";
import { ChevronIcon, LogoutIcon } from "./icons";
import { getInitials } from "../avatar";

// One entry per tab. Dashboard.tsx owns the list of tabs; the sidebar is a
// "dumb" component that only renders what it is given and reports clicks
// back up. That keeps all tab logic in one place (Dashboard.tsx).
export interface SidebarTab {
  id: string;
  label: string;
  icon: ReactNode;
}

interface SidebarProps {
  user: User;
  tabs: SidebarTab[];
  activeTab: string;
  onSelectTab: (id: string) => void;
  // Whether the sidebar is currently retracted to its slim icon-only form.
  // The state lives in Dashboard.tsx (it also drives the grid width there).
  collapsed: boolean;
  onToggle: () => void;
  onLogout: () => void;
  // Optional: when provided, the avatar becomes a button that calls this
  // (Dashboard passes it only if the user actually has a Profile tab, so
  // recruiters keep a plain, non-clickable avatar).
  onAvatarClick?: () => void;
  // Blob URL of the user's uploaded photo (owned by Dashboard.tsx), or
  // null/undefined to fall back to their initials.
  photoUrl?: string | null;
}

export default function Sidebar({
  user,
  tabs,
  activeTab,
  onSelectTab,
  collapsed,
  onToggle,
  onLogout,
  onAvatarClick,
  photoUrl,
}: SidebarProps) {
  const isSeeker = user.role === "job_seeker";
  const roleLabel = isSeeker ? "Job seeker" : "Recruiter";

  // The avatar shows the uploaded photo if there is one, otherwise the
  // user's initials. The alt text is empty because the photo is decorative:
  // the surrounding button / role="img" element already carries the label.
  const avatarContent = photoUrl ? (
    <img className="cc-photo-img" src={photoUrl} alt="" />
  ) : (
    getInitials(user.full_name)
  );
  const avatarClass = `cc-photo ${photoUrl ? "has-photo" : ""}`;

  return (
    <aside className="cc-sidebar">
      <div className="cc-sidebar-top">
        <div className="cc-brand">
          <span className="cc-brand-first">Career</span>
          <span className="cc-brand-second">Connect</span>
        </div>

        {/* aria-expanded tells screen readers whether the sidebar is open;
            the label flips so the button always says what it WILL do. */}
        <button
          type="button"
          className="cc-collapse"
          onClick={onToggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <ChevronIcon />
        </button>
      </div>

      {/* Stays visible when collapsed (CSS shrinks it to a small avatar).
          If a click handler was given it is a real <button> (keyboard
          focusable, announced as a button); otherwise a plain decorative div. */}
      {onAvatarClick ? (
        <button
          type="button"
          className={`${avatarClass} is-clickable`}
          onClick={onAvatarClick}
          aria-label="Open your profile"
          title="Open your profile"
        >
          {avatarContent}
        </button>
      ) : (
        <div className={avatarClass} role="img" aria-label="Profile photo placeholder">
          {avatarContent}
        </div>
      )}

      {/* Name / role / email are hidden by CSS while collapsed — there is
          no room for them in the slim bar. */}
      <div className="cc-identity">
        <p className="cc-name">{user.full_name}</p>
        <p className="cc-role">{roleLabel}</p>
        <p className="cc-email">{user.email}</p>
      </div>

      <nav className="cc-nav" aria-label="Dashboard sections">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`cc-nav-item ${tab.id === activeTab ? "is-active" : ""}`}
            aria-current={tab.id === activeTab ? "page" : undefined}
            // While collapsed only the icon is visible, so show the label
            // as a hover tooltip.
            title={collapsed ? tab.label : undefined}
            onClick={() => onSelectTab(tab.id)}
          >
            <span className="cc-nav-icon">{tab.icon}</span>
            {/* The label is visually hidden (not removed) when collapsed so
                screen readers still announce it. */}
            <span className="cc-nav-label">{tab.label}</span>
          </button>
        ))}
      </nav>

      <button
        type="button"
        className="cc-nav-item cc-logout"
        onClick={onLogout}
        title={collapsed ? "Log out" : undefined}
      >
        <span className="cc-nav-icon">
          <LogoutIcon />
        </span>
        <span className="cc-nav-label">Log out</span>
      </button>
    </aside>
  );
}
