import { useEffect, useState } from "react";
import type { ApplicationOut } from "../../api";
import { listMyApplications } from "../../api";
import type { ApplicationHistoryEntry } from "../../applicantsApi";
import { getApplicationHistory } from "../../applicantsApi";
import "../../styles/myApplications.css";

// The "My Applications" tab (job seekers only): every job the user applied to,
// its CURRENT status (Applied / Under Review / Interview / Offered / Rejected)
// and, on request, the timeline of status changes.
//
// The recruiter changes statuses from their side (RecruiterApplicants.tsx);
// this tab only READS them, so it has a Refresh button to pick up changes
// made since the page was opened.
//
// Backend routes used (both already exist and are protected):
//   GET /api/applications/mine            -> listMyApplications()
//   GET /api/applications/{id}/history    -> getApplicationHistory()

// Backend timestamps are UTC without a timezone suffix, so add "Z" before
// handing them to Date; otherwise the browser would read them as local time.
// (Same helper as RecruiterApplicants.tsx, kept local so the two tabs stay
// independent.)
function formatDate(value: string): string {
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  const date = new Date(hasTimezone ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

// "Under Review" -> "is-under-review": a CSS hook for the badge's colored dot.
function statusClass(status: string): string {
  return `is-${status.toLowerCase().replace(/\s+/g, "-")}`;
}

// ---------------------------------------------------------------------------
// Timeline of status changes for ONE application. It is only mounted while the
// "View history" section is open, so history is fetched on demand, not for
// every card up front.
// ---------------------------------------------------------------------------
interface HistoryProps {
  applicationId: number;
  token: string;
  // Bumped by the parent's Refresh button so an open timeline reloads too.
  refreshKey: number;
}

function ApplicationHistory({ applicationId, token, refreshKey }: HistoryProps) {
  const [entries, setEntries] = useState<ApplicationHistoryEntry[] | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0); // bumped by "Try again"

  useEffect(() => {
    // Drop the answer if the user closes the section (or a newer request
    // started) before this one finishes.
    let cancelled = false;
    setError("");
    getApplicationHistory(applicationId, token)
      .then((data) => {
        if (!cancelled) setEntries(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [applicationId, token, refreshKey, attempt]);

  if (error) {
    return (
      <div className="cc-app-history">
        <p className="cc-error" role="alert">{error}</p>
        <button type="button" className="cc-app-toggle" onClick={() => setAttempt((n) => n + 1)}>
          Try again
        </button>
      </div>
    );
  }

  if (entries === null) {
    return (
      <div className="cc-app-history">
        <p className="cc-muted" role="status">Loading history…</p>
      </div>
    );
  }

  return (
    <div className="cc-app-history">
      <h4 className="cc-app-history-title">Status history</h4>
      <ol className="cc-app-history-list">
        {entries.map((entry, index) => (
          <li key={index} className="cc-app-history-item">
            <span>
              {/* old_status is null for the very first entry (the submission). */}
              {entry.old_status === null
                ? `Application submitted: ${entry.new_status}`
                : `${entry.old_status} → ${entry.new_status}`}
            </span>
            <span className="cc-app-meta">{formatDate(entry.changed_at)}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

// ---------------------------------------------------------------------------
// The tab itself
// ---------------------------------------------------------------------------
export default function MyApplicationsTab({ token }: { token: string }) {
  // null = the first load has not finished yet.
  const [applications, setApplications] = useState<ApplicationOut[] | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  // Changing this number re-runs the fetch below (Refresh / Try again).
  const [reloadKey, setReloadKey] = useState(0);
  // Only one card's history is open at a time.
  const [openHistoryId, setOpenHistoryId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError("");
    listMyApplications(token)
      .then((data) => {
        if (!cancelled) setApplications(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setRefreshing(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, reloadKey]);

  function reload() {
    setRefreshing(true);
    setReloadKey((n) => n + 1);
  }

  return (
    <>
      <header className="cc-main-head">
        <div>
          <h1 className="cc-title">My Applications</h1>
          <p className="cc-subtitle">Track every job you applied to and where it stands.</p>
        </div>
      </header>

      <section className="cc-section" aria-label="My applications">
        <div className="cc-app-section-head">
          <h2 className="cc-section-title">
            Applications{applications ? ` (${applications.length})` : ""}
          </h2>
          <button
            type="button"
            className="cc-upload-btn cc-btn-secondary"
            onClick={reload}
            disabled={refreshing}
          >
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>

        {applications === null && !error && (
          <p className="cc-muted" role="status">Loading your applications…</p>
        )}

        {error && (
          <p className="cc-error" role="alert">{error}</p>
        )}

        {applications !== null && applications.length === 0 && (
          <p className="cc-muted">
            You haven't applied to any jobs yet. Find one in the Job Dashboard.
          </p>
        )}

        {applications !== null && applications.length > 0 && (
          <ul className="cc-apps-list">
            {applications.map((application) => {
              const historyOpen = openHistoryId === application.id;
              const historyId = `application-history-${application.id}`;
              return (
                <li key={application.id} className="cc-app-card">
                  <div className="cc-app-card-head">
                    <div>
                      <h3 className="cc-app-title">{application.job_title}</h3>
                      <p className="cc-app-meta">{application.company}</p>
                    </div>
                    {/* The colored dot is decoration; the status is always
                        written out, so color is never the only signal. */}
                    <span className={`cc-app-status ${statusClass(application.status)}`}>
                      <span className="cc-visually-hidden">Status: </span>
                      {application.status}
                    </span>
                  </div>

                  <p className="cc-app-meta">
                    Applied {formatDate(application.applied_at)} · Last updated{" "}
                    {formatDate(application.updated_at)}
                  </p>
                  <p className="cc-app-meta">
                    Resume: {application.resume_filename ?? "Resume was deleted after applying"}
                  </p>

                  <button
                    type="button"
                    className="cc-app-toggle"
                    aria-expanded={historyOpen}
                    aria-controls={historyId}
                    onClick={() => setOpenHistoryId(historyOpen ? null : application.id)}
                  >
                    {historyOpen ? "Hide history" : "View history"}
                  </button>

                  {historyOpen && (
                    <div id={historyId}>
                      <ApplicationHistory
                        applicationId={application.id}
                        token={token}
                        refreshKey={reloadKey}
                      />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </>
  );
}
