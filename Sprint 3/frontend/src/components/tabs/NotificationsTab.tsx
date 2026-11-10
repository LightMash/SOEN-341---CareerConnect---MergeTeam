import { useEffect, useState } from "react";
import type { AppNotification, NotificationType } from "../../notificationsApi";
import {
  deleteNotification,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../../notificationsApi";
import "../../styles/notifications.css";

// The "Notifications" tab (every role): the in-app inbox.
//
// Backend routes used (all protected, all scoped to the logged-in user):
//   GET/POST/DELETE /api/notifications...

interface NotificationsTabProps {
  token: string;
  // Called after anything that changes the unread count, so the sidebar badge
  // (owned by Dashboard.tsx) refreshes immediately instead of at the next poll.
  onChanged: () => void;
}

// Backend timestamps are UTC without a timezone suffix; add "Z" so the browser
// does not read them as local time (same helper as MyApplicationsTab.tsx).
function formatDate(value: string): string {
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  const date = new Date(hasTimezone ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

// A short text label per type, so meaning never depends on color alone.
const TYPE_LABEL: Record<NotificationType, string> = {
  new_application: "New application",
  status_changed: "Status update",
  interview_invitation: "Interview",
};

export default function NotificationsTab({ token, onChanged }: NotificationsTabProps) {
  const [notifications, setNotifications] = useState<AppNotification[] | null>(null);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0); // bumped to re-fetch everything

  useEffect(() => {
    let cancelled = false;
    listNotifications(token)
      .then((list) => {
        if (cancelled) return;
        setNotifications(list);
        setError("");
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [token, reloadKey]);

  function reload() {
    setReloadKey((n) => n + 1);
    onChanged();
  }

  // Runs an action, then reloads; any failure is shown instead of swallowed.
  async function run(action: () => Promise<unknown>) {
    try {
      await action();
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  const unreadCount = notifications?.filter((n) => !n.is_read).length ?? 0;

  return (
    <>
      <header className="cc-main-head">
        <div>
          <h1 className="cc-title">Notifications</h1>
          <p className="cc-subtitle">Application updates and interview invitations.</p>
        </div>
      </header>

      {error && (
        <p className="cc-error" role="alert">
          {error}
        </p>
      )}

      {/* ---------------- Inbox ---------------- */}
      <section className="cc-section" aria-label="Notifications">
        <div className="cc-notif-head">
          <h2 className="cc-section-title">
            Inbox{notifications ? ` (${unreadCount} unread)` : ""}
          </h2>
          <button
            type="button"
            className="cc-upload-btn cc-btn-secondary"
            onClick={() => run(() => markAllNotificationsRead(token))}
            disabled={unreadCount === 0}
          >
            Mark all as read
          </button>
        </div>

        {notifications === null && !error && (
          <p className="cc-muted" role="status">
            Loading…
          </p>
        )}
        {notifications !== null && notifications.length === 0 && (
          <p className="cc-muted">Nothing yet. Updates about your applications will show up here.</p>
        )}

        {notifications !== null && notifications.length > 0 && (
          <ul className="cc-notif-list">
            {notifications.map((n) => (
              <li key={n.id} className={`cc-notif ${n.is_read ? "" : "is-unread"}`}>
                <div className="cc-notif-body">
                  <p className="cc-notif-title">
                    <span className="cc-notif-type">{TYPE_LABEL[n.type]}</span>
                    {!n.is_read && <span className="cc-visually-hidden"> (unread)</span>}
                    {n.title}
                  </p>
                  <p className="cc-notif-message">{n.message}</p>
                  <p className="cc-notif-time">{formatDate(n.created_at)}</p>
                </div>
                <div className="cc-notif-actions">
                  {!n.is_read && (
                    <button
                      type="button"
                      className="cc-app-toggle"
                      onClick={() => run(() => markNotificationRead(n.id, token))}
                    >
                      Mark read
                    </button>
                  )}
                  <button
                    type="button"
                    className="cc-app-toggle"
                    onClick={() => run(() => deleteNotification(n.id, token))}
                    aria-label={`Delete notification: ${n.title}`}
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
