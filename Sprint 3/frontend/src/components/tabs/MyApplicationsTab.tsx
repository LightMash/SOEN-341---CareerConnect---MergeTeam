import { useEffect, useState } from "react";
import type { ApplicationOut, ApplicationStats } from "../../api";
import { listMyApplications, getMyApplicationStats } from "../../api";
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
// Backend routes used (all already exist and are protected):
//   GET /api/applications/mine            -> listMyApplications()
//   GET /api/applications/mine/stats      -> getMyApplicationStats()
//   GET /api/applications/{id}/history    -> getApplicationHistory()

// Pipeline order, same as APPLICATION_STATUSES in the backend. Used for the
// filter dropdown so it works before the stats have loaded.
const APPLICATION_STATUSES = ["Applied", "Under Review", "Interview", "Offered", "Rejected"];

type SortOrder = "newest" | "oldest";
type ActivityRange = "weekly" | "monthly";

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

// period_start is a plain date ("2026-11-09"), which JS parses as UTC midnight.
// Formatting it in Montreal time would show the previous day (Nov 8), so the
// formatter is pinned to UTC.
function formatPeriod(value: string, options: Intl.DateTimeFormatOptions): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", { ...options, timeZone: "UTC" }).format(date);
}

// "Under Review" -> "is-under-review": a CSS hook for the status colour.
function statusClass(status: string): string {
  return `is-${status.toLowerCase().replace(/\s+/g, "-")}`;
}

// ---------------------------------------------------------------------------
// Status summary: one tile for the total plus one per status. Each tile is
// also a shortcut for the status filter (clicking the active one clears it).
// ---------------------------------------------------------------------------
interface SummaryProps {
  stats: ApplicationStats;
  activeStatus: string;
  onSelect: (status: string) => void;
}

function StatusSummary({ stats, activeStatus, onSelect }: SummaryProps) {
  // The backend seeds all five statuses (zeros included) in pipeline order,
  // so Object.entries gives a stable tile order.
  const tiles: [string, number][] = [["All", stats.total], ...Object.entries(stats.by_status)];

  return (
    <ul className="cc-app-summary">
      {tiles.map(([status, count]) => {
        const isAll = status === "All";
        const active = activeStatus === status;
        return (
          <li key={status}>
            <button
              type="button"
              className={`cc-app-summary-tile ${isAll ? "" : statusClass(status)}`}
              aria-pressed={active}
              onClick={() => onSelect(active && !isAll ? "All" : status)}
            >
              <span className="cc-app-summary-count">{count}</span>
              <span className="cc-app-summary-label">
                {/* Dot colour comes from the tile's is-<status> class. */}
                {!isAll && <span className="cc-app-dot" aria-hidden="true" />}
                {isAll ? "Total" : status}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Activity chart: applications submitted per week (last 10) or per month
// (last 12). Plain CSS bars: heights are a percentage of the busiest period.
// ---------------------------------------------------------------------------
function ActivityChart({ stats }: { stats: ApplicationStats }) {
  // Only this chart cares about the range, so the state lives here.
  const [range, setRange] = useState<ActivityRange>("weekly");

  const periods = stats[range];
  // At least 1 so an all-zero range doesn't divide by zero.
  const max = Math.max(1, ...periods.map((p) => p.count));
  const totalInRange = periods.reduce((sum, p) => sum + p.count, 0);
  const rangeText = range === "weekly" ? "last 10 weeks" : "last 12 months";

  // Short label under the bar, and a full name for screen readers.
  const shortLabel = (start: string) =>
    range === "weekly"
      ? formatPeriod(start, { month: "short", day: "numeric" })
      : formatPeriod(start, { month: "short" });
  const fullLabel = (start: string) =>
    range === "weekly"
      ? `Week of ${formatPeriod(start, { dateStyle: "medium" })}`
      : formatPeriod(start, { month: "long", year: "numeric" });

  return (
    <>
      <div className="cc-app-section-head">
        <div>
          <h2 className="cc-section-title">Activity</h2>
          <p className="cc-app-meta">
            {totalInRange} application{totalInRange === 1 ? "" : "s"} in the {rangeText}
          </p>
        </div>
        <div className="cc-app-range" role="group" aria-label="Activity range">
          <button
            type="button"
            className="cc-app-range-btn"
            aria-pressed={range === "weekly"}
            onClick={() => setRange("weekly")}
          >
            Weekly
          </button>
          <button
            type="button"
            className="cc-app-range-btn"
            aria-pressed={range === "monthly"}
            onClick={() => setRange("monthly")}
          >
            Monthly
          </button>
        </div>
      </div>

      {/* Oldest period first, current one last (backend order). The visible
          numbers/labels are aria-hidden; each column has one readable sentence. */}
      <ol className="cc-app-chart">
        {periods.map((p) => (
          <li key={p.period_start} className="cc-app-chart-col">
            <span className="cc-app-chart-value" aria-hidden="true">
              {p.count > 0 ? p.count : ""}
            </span>
            <span className="cc-app-chart-track" aria-hidden="true">
              <span
                className={`cc-app-chart-bar ${p.count === 0 ? "is-empty" : ""}`}
                style={{ height: `${(p.count / max) * 100}%` }}
              />
            </span>
            <span className="cc-app-chart-label" aria-hidden="true">
              {shortLabel(p.period_start)}
            </span>
            <span className="cc-visually-hidden">
              {fullLabel(p.period_start)}: {p.count} application{p.count === 1 ? "" : "s"}
            </span>
          </li>
        ))}
      </ol>
    </>
  );
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
  // Dashboard (status filter, order, stats)
  const [statusFilter, setStatusFilter] = useState("All");
  const [sortOrder, setSortOrder] = useState<SortOrder>("newest");
  const [stats, setStats] = useState<ApplicationStats | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError("");
    Promise.all([listMyApplications(token), getMyApplicationStats(token)])
      .then(([data, statsData]) => {
        if (cancelled) return;
        setApplications(data);
        setStats(statsData);
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

  // filter() returns a new array, so sort() doesn't mutate state.
  const visible = (applications ?? [])
    .filter((a) => statusFilter === "All" || a.status === statusFilter)
    .sort((a, b) => {
      const diff = new Date(a.applied_at).getTime() - new Date(b.applied_at).getTime();
      return sortOrder === "newest" ? -diff : diff;
    });

  const hasApplications = applications !== null && applications.length > 0;
  const isFiltered = statusFilter !== "All";

  return (
    <>
      <header className="cc-main-head">
        <div>
          <h1 className="cc-title">My Applications</h1>
          <p className="cc-subtitle">Track every job you applied to and where it stands.</p>
        </div>
      </header>

      {/* Summary + activity only once there is something to summarize. */}
      {stats !== null && hasApplications && (
        <>
          <section className="cc-section" aria-label="Applications by status">
            <h2 className="cc-section-title">Summary</h2>
            <StatusSummary stats={stats} activeStatus={statusFilter} onSelect={setStatusFilter} />
          </section>

          <section className="cc-section" aria-label="Application activity">
            <ActivityChart stats={stats} />
          </section>
        </>
      )}

      <section className="cc-section" aria-label="My applications">
        <div className="cc-app-section-head">
          <h2 className="cc-section-title">
            Applications
            {applications &&
              (isFiltered
                ? ` (${visible.length} of ${applications.length})`
                : ` (${applications.length})`)}
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

        {hasApplications && (
          <div className="cc-app-toolbar">
            <label className="cc-app-control">
              <span>Status</span>
              <select
                className="cc-input"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="All">All statuses</option>
                {APPLICATION_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
            <label className="cc-app-control">
              <span>Sort by</span>
              <select
                className="cc-input"
                value={sortOrder}
                // The options below are the only two values, so the cast is safe.
                onChange={(e) => setSortOrder(e.target.value as SortOrder)}
              >
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
              </select>
            </label>
          </div>
        )}

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

        {/* Has applications, but none match the current filter. */}
        {hasApplications && visible.length === 0 && (
          <div className="cc-app-empty">
            <p className="cc-muted">No applications with the status “{statusFilter}”.</p>
            <button type="button" className="cc-app-toggle" onClick={() => setStatusFilter("All")}>
              Show all applications
            </button>
          </div>
        )}

        {visible.length > 0 && (
          <ul className="cc-apps-list">
            {visible.map((application) => {
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
