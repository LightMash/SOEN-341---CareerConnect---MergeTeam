import { useEffect, useRef, useState } from "react";

import {
  APPLICATION_STATUSES,
  getApplicants,
  getApplicationHistory,
  updateApplicationStatus,
  type Applicant,
  type ApplicationHistoryEntry,
  type ApplicationStatus,
} from "../../applicantsApi";

import "../../styles/applicants.css";

interface RecruiterApplicantsProps {
  jobId: number;
  token: string;
}

// Backend timestamps may be UTC without an explicit timezone.
// Treat those timestamps as UTC before displaying them locally.
function formatDate(value: string): string {
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  const normalized = hasTimezone ? value : `${value}Z`;
  const date = new Date(normalized);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-CA", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function timestamp(value: string): number {
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  const date = new Date(hasTimezone ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? 0 : date.getTime();
}

function sortNewestFirst(items: Applicant[]): Applicant[] {
  return [...items].sort(
    (a, b) =>
      timestamp(b.applied_at) - timestamp(a.applied_at) ||
      b.id - a.id
  );
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
}

// ------------------------------------------------------------
// Status history: fetched only while expanded.
// ------------------------------------------------------------

interface ApplicantHistoryProps {
  applicationId: number;
  applicantId: number;
  token: string;
  refreshKey: number;
}

function ApplicantHistory({
  applicationId,
  applicantId,
  token,
  refreshKey,
}: ApplicantHistoryProps) {
  const [history, setHistory] = useState<
    ApplicationHistoryEntry[]
  >([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let active = true;

    setLoading(true);
    setError(null);

    getApplicationHistory(applicationId, token)
      .then((entries) => {
        if (active) {
          setHistory(
            [...entries].sort(
              (a, b) =>
                timestamp(b.changed_at) -
                timestamp(a.changed_at)
            )
          );
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setError(getErrorMessage(err));
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [applicationId, token, refreshKey, retryKey]);

  if (loading) {
    return (
      <div className="cc-applicant-history">
        <p role="status">Loading status history...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="cc-applicant-history">
        <p role="alert">{error}</p>
        <button
          type="button"
          className="cc-small-btn"
          onClick={() => setRetryKey((key) => key + 1)}
        >
          Retry history
        </button>
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div className="cc-applicant-history">
        <p>No status history available.</p>
      </div>
    );
  }

  return (
    <div className="cc-applicant-history">
      <h5>Status history</h5>

      <ul className="cc-applicant-history-list">
        {history.map((entry, index) => {
          const actor =
            entry.changed_by === applicantId
              ? "Applicant"
              : "Recruiter";

          const isInitial = entry.old_status === null;

          return (
            <li
              key={`${entry.changed_at}-${index}`}
              className="cc-applicant-history-item"
            >
              <strong>
                {isInitial
                  ? `Application submitted — ${entry.new_status}`
                  : `${entry.old_status} → ${entry.new_status}`}
              </strong>

              <span className="cc-applicant-meta">
                {formatDate(entry.changed_at)}
                {" · "}
                {actor}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ------------------------------------------------------------
// Main applicants panel
// ------------------------------------------------------------

export default function RecruiterApplicants({
  jobId,
  token,
}: RecruiterApplicantsProps) {
  const [applicants, setApplicants] = useState<Applicant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  const [savingIds, setSavingIds] = useState<number[]>([]);

  const [pendingStatuses, setPendingStatuses] = useState<
    Record<number, ApplicationStatus>
  >({});

  const [statusErrors, setStatusErrors] = useState<
    Record<number, string | null>
  >({});

  const [statusSuccess, setStatusSuccess] = useState<
    Record<number, boolean>
  >({});

  const [expandedHistoryId, setExpandedHistoryId] = useState<
    number | null
  >(null);

  const [historyRefreshKeys, setHistoryRefreshKeys] = useState<
    Record<number, number>
  >({});

  // Synchronous guard against duplicate requests.
  const savingRef = useRef<Set<number>>(new Set());

  // ----------------------------------------------------------
  // Load applicants when the panel mounts or Retry is clicked.
  // ----------------------------------------------------------

  useEffect(() => {
    let active = true;

    setLoading(true);
    setError(null);

    getApplicants(jobId, token)
      .then((data) => {
        if (active) {
          setApplicants(sortNewestFirst(data));
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setError(getErrorMessage(err));
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [jobId, token, retryKey]);

  // ----------------------------------------------------------
  // Save a status immediately when selected.
  // ----------------------------------------------------------

  async function handleStatusChange(
    applicant: Applicant,
    newStatus: ApplicationStatus
  ) {
    const id = applicant.id;

    if (newStatus === applicant.status) return;
    if (savingRef.current.has(id)) return;

    savingRef.current.add(id);

    setSavingIds((prev) => [...prev, id]);

    setPendingStatuses((prev) => ({
      ...prev,
      [id]: newStatus,
    }));

    setStatusErrors((prev) => ({
      ...prev,
      [id]: null,
    }));

    setStatusSuccess((prev) => ({
      ...prev,
      [id]: false,
    }));

    try {
      const updated = await updateApplicationStatus(
        id,
        newStatus,
        token
      );

      // Only the backend-confirmed value becomes saved state.
      setApplicants((prev) =>
        prev.map((item) =>
          item.id === id ? updated : item
        )
      );

      setStatusSuccess((prev) => ({
        ...prev,
        [id]: true,
      }));

      // If history is currently expanded, its effect runs again.
      setHistoryRefreshKeys((prev) => ({
        ...prev,
        [id]: (prev[id] ?? 0) + 1,
      }));

    } catch (err: unknown) {
      setStatusErrors((prev) => ({
        ...prev,
        [id]: getErrorMessage(err),
      }));

      // No rollback request is necessary:
      // applicant.status was never changed locally.
    } finally {
      savingRef.current.delete(id);

      setSavingIds((prev) =>
        prev.filter((savingId) => savingId !== id)
      );

      setPendingStatuses((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    }
  }

  function toggleHistory(applicationId: number) {
    setExpandedHistoryId((current) =>
      current === applicationId ? null : applicationId
    );
  }

  // ----------------------------------------------------------
  // Loading, error and empty states
  // ----------------------------------------------------------

  if (loading) {
    return (
      <section className="cc-applicants" aria-busy="true">
        <p role="status">Loading applicants...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="cc-applicants">
        <p role="alert">{error}</p>

        <button
          type="button"
          className="cc-small-btn"
          onClick={() => setRetryKey((key) => key + 1)}
        >
          Retry
        </button>
      </section>
    );
  }

  if (applicants.length === 0) {
    return (
      <section className="cc-applicants">
        <h4>Applicants</h4>
        <p>No applications yet for this posting.</p>
      </section>
    );
  }

  // ----------------------------------------------------------
  // Applicant list
  // ----------------------------------------------------------

  return (
    <section className="cc-applicants">
      <div className="cc-applicants-heading">
        <h4>Applicants</h4>

        <span className="cc-applicant-meta">
          {applicants.length}{" "}
          {applicants.length === 1
            ? "applicant"
            : "applicants"}
        </span>
      </div>

      <ul className="cc-applicants-list">
        {applicants.map((applicant) => {
          const id = applicant.id;
          const saving = savingIds.includes(id);
          const historyOpen = expandedHistoryId === id;

          const selectedStatus =
            pendingStatuses[id] ?? applicant.status;

          return (
            <li
              key={id}
              className="cc-applicant-card"
            >
              <div className="cc-applicant-header">
                <div>
                  <h5 className="cc-applicant-name">
                    {applicant.applicant_name}
                  </h5>

                  <p className="cc-applicant-meta">
                    {applicant.applicant_email}
                  </p>
                </div>
              </div>

              <div className="cc-applicant-details">
                <p className="cc-applicant-meta">
                  <strong>Resume:</strong>{" "}
                  {applicant.resume_filename ??
                    "No resume"}
                </p>

                <p className="cc-applicant-meta">
                  <strong>Applied:</strong>{" "}
                  {formatDate(applicant.applied_at)}
                </p>
              </div>

              <div className="cc-applicant-status-row">
                <label htmlFor={`application-status-${id}`}>
                  Application status
                </label>

                <select
                  id={`application-status-${id}`}
                  className="cc-applicant-status"
                  value={selectedStatus}
                  disabled={saving}
                  onChange={(event) =>
                    handleStatusChange(
                      applicant,
                      event.target
                        .value as ApplicationStatus
                    )
                  }
                >
                  {APPLICATION_STATUSES.map((status) => (
                    <option key={status} value={status}>
                      {status}
                    </option>
                  ))}
                </select>

                {saving && (
                  <span
                    className="cc-applicant-meta"
                    role="status"
                  >
                    Saving...
                  </span>
                )}

                {!saving && statusSuccess[id] && (
                  <span
                    className="cc-applicant-success"
                    role="status"
                  >
                    Status saved
                  </span>
                )}

                {!saving && statusErrors[id] && (
                  <p
                    className="cc-applicant-error"
                    role="alert"
                  >
                    {statusErrors[id]}
                    {" "}
                    Previous status restored.
                  </p>
                )}
              </div>

              <button
                type="button"
                className="cc-small-btn cc-history-toggle"
                aria-expanded={historyOpen}
                aria-controls={`application-history-${id}`}
                onClick={() => toggleHistory(id)}
              >
                {historyOpen
                  ? "Hide history"
                  : "View history"}
              </button>

              {historyOpen && (
                <div id={`application-history-${id}`}>
                  <ApplicantHistory
                    applicationId={id}
                    applicantId={applicant.applicant_id}
                    token={token}
                    refreshKey={
                      historyRefreshKeys[id] ?? 0
                    }
                  />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
