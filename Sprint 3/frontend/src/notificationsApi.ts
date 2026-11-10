const API_BASE = "http://localhost:5000/api";

// These types mirror backend/schemas/notification.py. If you change a field
// there, change it here too.

export type NotificationType =
  | "new_application"
  | "status_changed"
  | "interview_invitation";

export interface AppNotification {
  id: number;
  type: NotificationType;
  title: string;
  message: string;
  application_id: number | null;
  is_read: boolean;
  created_at: string; // UTC, no timezone suffix (see formatDate in the tab)
}

// Same request pattern as applicantsApi.ts / postingsApi.ts.
async function send<T>(
  path: string,
  token: string,
  method = "GET",
  body?: unknown
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // 204 No Content (deletes) has no body to parse.
  const data = response.status === 204 ? {} : await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail
              .map((d: { msg?: string }) => (d.msg ?? "Invalid value").replace(/^Value error, /, ""))
              .join(". ")
          : "Something went wrong. Please try again.";
    throw new Error(detail);
  }

  return data as T;
}

// --- Notifications ---------------------------------------------------------
export function listNotifications(token: string): Promise<AppNotification[]> {
  return send<AppNotification[]>("/notifications", token);
}

// What the sidebar badge polls.
export function getUnreadCount(token: string): Promise<{ unread: number }> {
  return send<{ unread: number }>("/notifications/unread-count", token);
}

export function markNotificationRead(id: number, token: string): Promise<AppNotification> {
  return send<AppNotification>(`/notifications/${id}/read`, token, "POST");
}

export function markAllNotificationsRead(token: string): Promise<{ updated: number }> {
  return send<{ updated: number }>("/notifications/read-all", token, "POST");
}

export function deleteNotification(id: number, token: string): Promise<void> {
  return send<void>(`/notifications/${id}`, token, "DELETE");
}
