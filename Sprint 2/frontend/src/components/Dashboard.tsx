import { useEffect, useState } from "react";
import type { Role, User } from "../api";
import { getProfilePhoto } from "../api";
import Sidebar from "./Sidebar";
import type { SidebarTab } from "./Sidebar";
import { BriefcaseIcon, UserIcon } from "./icons";
import JobDashboardTab from "./tabs/JobDashboardTab";
import ProfileTab from "./tabs/ProfileTab";
import RecruiterProfileTab from "./tabs/RecruiterProfileTab";

// Dashboard is now a thin "shell": a retractable sidebar plus whichever tab
// is active. It no longer contains any resume logic — that moved to
// ResumeManager.tsx, which the Profile tab renders.

interface DashboardProps {
  user: User;
  // The logged-in user's JWT (from App.tsx's `token` state). Passed down to
  // every tab that talks to a protected backend endpoint, which read it from
  // the `Authorization: Bearer <token>` header.
  token: string;
  onLogout: () => void;
}

type TabId = "jobs" | "profile";

interface TabDef extends SidebarTab {
  id: TabId;
  roles: Role[]; // which kinds of users get to see this tab
}

// ADDING A FUTURE TAB (e.g. "Applications"):
//   1. add its id to TabId above,
//   2. add one entry to this array,
//   3. add one case to renderTab() below.
// The sidebar, the role filtering and the collapsed (icon-only) mode all
// pick it up automatically.
const TABS: TabDef[] = [
  {
    id: "jobs",
    label: "Job Dashboard",
    icon: <BriefcaseIcon />,
    roles: ["job_seeker", "recruiter"],
  },
  {
    id: "profile",
    label: "Profile",
    icon: <UserIcon />,
    // Everyone has a Profile tab (it holds the account photo). What it SHOWS
    // differs by role: see renderTab() below.
    roles: ["job_seeker", "recruiter"],
  },
];

// localStorage key used to remember whether the sidebar was collapsed.
const COLLAPSE_KEY = "cc_sidebar_collapsed";

export default function Dashboard({ user, token, onLogout }: DashboardProps) {
  // Only show the tabs this user's role is allowed to see.
  const visibleTabs = TABS.filter((tab) => tab.roles.includes(user.role));

  // Job Dashboard is the default landing tab, same as the old dashboard was.
  const [activeTab, setActiveTab] = useState<TabId>("jobs");

  // Remember the sidebar state across visits. Reading storage is done in a
  // lazy initializer (runs once, on first render) and wrapped in try/catch,
  // because localStorage can throw in private windows or with blocked storage.
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === "1";
    } catch {
      return false;
    }
  });

  // The user's profile photo as a temporary blob: URL (null = none). It lives
  // HERE, in the shared parent, because two places show it: the sidebar avatar
  // and the Profile tab's photo block. When the Profile tab uploads a new one,
  // it reports back through handlePhotoChange and the sidebar updates too.
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);

  // Load the saved photo once on mount (every role can have one).
  useEffect(() => {
    // If the component goes away before the request finishes, free the URL
    // instead of setting state on something that no longer exists.
    let cancelled = false;
    getProfilePhoto(token)
      .then((url) => {
        if (cancelled) {
          if (url) URL.revokeObjectURL(url);
        } else {
          setPhotoUrl(url);
        }
      })
      .catch(() => {
        /* no photo is a fine fallback: the avatar just shows initials */
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  function handlePhotoChange(newUrl: string | null) {
    // Blob URLs keep their bytes in memory until revoked, so release the one
    // being replaced. (Revoking twice is harmless, which matters because
    // React may run this updater twice in development.)
    setPhotoUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return newUrl;
    });
  }

  function toggleSidebar() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        /* ignore — the sidebar still works, it just won't be remembered */
      }
      return next;
    });
  }

  // Picks what to show in the main area. The tab that is not active is
  // unmounted, so each tab re-fetches its own data when you switch to it.
  function renderTab() {
    switch (activeTab) {
      case "profile":
        // Job seekers get the full profile + resumes; recruiters get just
        // the photo block (they have no professional profile or resumes).
        return user.role === "job_seeker" ? (
          <ProfileTab
            token={token}
            fullName={user.full_name}
            photoUrl={photoUrl}
            onPhotoChange={handlePhotoChange}
          />
        ) : (
          <RecruiterProfileTab
            token={token}
            fullName={user.full_name}
            photoUrl={photoUrl}
            onPhotoChange={handlePhotoChange}
          />
        );
      case "jobs":
      default:
        return <JobDashboardTab user={user} />;
    }
  }

  return (
    // `is-collapsed` flips a CSS variable (--cc-side-w) in index.css, which
    // is what actually narrows the sidebar column.
    <div className={`cc-dashboard ${collapsed ? "is-collapsed" : ""}`}>
      <Sidebar
        user={user}
        tabs={visibleTabs}
        activeTab={activeTab}
        // Sidebar only knows ids as plain strings; narrow back to TabId here.
        onSelectTab={(id) => setActiveTab(id as TabId)}
        collapsed={collapsed}
        onToggle={toggleSidebar}
        onLogout={onLogout}
        photoUrl={photoUrl}
        // Clicking the avatar jumps to the Profile tab (kept conditional so a
        // role without that tab would simply get a non-clickable avatar).
        onAvatarClick={
          visibleTabs.some((tab) => tab.id === "profile")
            ? () => setActiveTab("profile")
            : undefined
        }
      />

      <main className="cc-main">{renderTab()}</main>
    </div>
  );
}
