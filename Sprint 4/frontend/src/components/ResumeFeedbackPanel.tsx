import { useEffect, useRef, useState } from "react";
import type { Job, Resume } from "../api";
import { listJobs } from "../api";
import type { ResumeFeedback, Suggestion, SuggestionCategory, SuggestionPriority } from "../resumeFeedbackApi";
import { getLatestFeedback, requestFeedback } from "../resumeFeedbackApi";
import "../styles/resumeFeedback.css";

// AI Resume Feedback panel. Opened from a resume card in ResumeManager.
// Shows the latest saved review (no AI call), lets the user ask
// for a new one (optionally tailored to a job posting), and lets them accept
// or dismiss each suggestion and copy the accepted changes.
//
// Backend routes used:
//   GET  /api/resume/{id}/feedback   latest saved review (404 = none yet)
//   POST /api/resume/{id}/feedback   new review from Gemini, body {job_id}
//   GET  /api/jobs                   open postings, for the "tailor to" picker

interface ResumeFeedbackPanelProps {
  resume: Resume;
  token: string;
  onClose: () => void;
}

type Decision = "accepted" | "dismissed";

const PRIORITY_LABEL: Record<SuggestionPriority, string> = {
  high: "High impact",
  medium: "Medium impact",
  low: "Low impact",
};

const CATEGORY_LABEL: Record<SuggestionCategory, string> = {
  impact: "Impact",
  clarity: "Clarity",
  skills: "Skills",
  grammar: "Grammar",
  formatting: "Formatting",
  content: "Content",
};

// Same bands as the scoring rubric in backend/services/resume_feedback.py.
function scoreLabel(score: number): string {
  if (score >= 90) return "Ready to send";
  if (score >= 70) return "Good, a few fixes";
  if (score >= 50) return "Needs work";
  return "Major improvements needed";
}

function scoreBand(score: number): "high" | "mid" | "low" {
  if (score >= 70) return "high";
  if (score >= 50) return "mid";
  return "low";
}

// Backend timestamps are UTC without a timezone suffix (same helper as
// NotificationsTab.tsx).
function formatDate(value: string): string {
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  const date = new Date(hasTimezone ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

// Accept/dismiss choices are remembered in this browser per review, so they
// survive closing the panel.
function decisionsKey(feedbackId: number) {
  return `cc_feedback_decisions_${feedbackId}`;
}

function loadDecisions(feedbackId: number): Record<number, Decision> {
  try {
    return JSON.parse(localStorage.getItem(decisionsKey(feedbackId)) ?? "{}");
  } catch {
    return {};
  }
}

function saveDecisions(feedbackId: number, decisions: Record<number, Decision>) {
  try {
    localStorage.setItem(decisionsKey(feedbackId), JSON.stringify(decisions));
  } catch {
    /* not remembered, but the panel still works */
  }
}

// Plain-text list of accepted changes, for pasting into the user's resume.
function acceptedChangesText(suggestions: Suggestion[]): string {
  return suggestions
    .map((s) =>
      s.original
        ? `[${s.section}]\nReplace: ${s.original}\nWith:    ${s.suggested}`
        : `[${s.section}]\nAdd: ${s.suggested}`
    )
    .join("\n\n");
}

export default function ResumeFeedbackPanel({ resume, token, onClose }: ResumeFeedbackPanelProps) {
  // undefined = still loading the saved review; null = never reviewed.
  const [feedback, setFeedback] = useState<ResumeFeedback | null | undefined>(undefined);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState<number | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [decisions, setDecisions] = useState<Record<number, Decision>>({});
  const panelRef = useRef<HTMLElement>(null);

  // Scroll the panel into view when it opens (it renders below the resume grid).
  useEffect(() => {
    panelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [resume.id]);

  // Load the saved review for this resume (no AI call).
  useEffect(() => {
    let cancelled = false;
    setFeedback(undefined);
    setError("");
    getLatestFeedback(resume.id, token)
      .then((result) => {
        if (cancelled) return;
        setFeedback(result);
        setDecisions(result ? loadDecisions(result.id) : {});
        if (result?.job_id) setJobId(result.job_id);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setFeedback(null);
          setError(err.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [resume.id, token]);

  // Open postings for the "tailor to a job" picker. Optional: if this fails
  // the user can still get general feedback, so the error is ignored.
  useEffect(() => {
    listJobs({}, token)
      .then(setJobs)
      .catch(() => setJobs([]));
  }, [token]);

  async function analyze() {
    setAnalyzing(true);
    setError("");
    setNotice("");
    try {
      const result = await requestFeedback(resume.id, jobId, token);
      setFeedback(result);
      setDecisions({}); // a new review starts with no decisions
    } catch (err) {
      // The backend already sends a user-friendly message (busy, unreadable file...).
      setError(err instanceof Error ? err.message : "Couldn't get feedback. Please try again.");
    } finally {
      setAnalyzing(false);
    }
  }

  function decide(suggestionId: number, decision: Decision | null) {
    if (!feedback) return;
    setDecisions((prev) => {
      const next = { ...prev };
      if (decision) next[suggestionId] = decision;
      else delete next[suggestionId];
      saveDecisions(feedback.id, next);
      return next;
    });
  }

  async function copyText(text: string, message: string) {
    try {
      await navigator.clipboard.writeText(text);
      setNotice(message);
    } catch {
      setError("Couldn't copy to the clipboard. Select the text and copy it manually.");
    }
  }

  const accepted = feedback?.suggestions.filter((s) => decisions[s.id] === "accepted") ?? [];
  const tailoredJob = feedback?.job_id ? jobs.find((j) => j.id === feedback.job_id) : undefined;
  const hasReview = feedback !== null && feedback !== undefined;

  return (
    <section ref={panelRef} className="cc-section cc-fb" aria-label={`AI feedback for ${resume.filename}`}>
      <div className="cc-fb-head">
        <div>
          <h2 className="cc-section-title">AI feedback</h2>
          <p className="cc-subtitle" title={resume.filename}>
            {resume.filename}
          </p>
        </div>
        <button type="button" className="cc-link" onClick={onClose}>
          Close
        </button>
      </div>

      {/* ---------------- Request a review ---------------- */}
      <div className="cc-fb-controls">
        <label className="cc-fb-label" htmlFor="cc-fb-job">
          Tailor to a job posting (optional)
        </label>
        <div className="cc-fb-controls-row">
          <select
            id="cc-fb-job"
            className="cc-fb-select"
            value={jobId ?? ""}
            onChange={(e) => setJobId(e.target.value ? Number(e.target.value) : null)}
            disabled={analyzing}
          >
            <option value="">General feedback</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title} at {job.company}
              </option>
            ))}
          </select>
          <button type="button" className="cc-upload-btn" onClick={analyze} disabled={analyzing}>
            {analyzing ? "Analyzing..." : hasReview ? "Analyze again" : "Get AI feedback"}
          </button>
        </div>
      </div>

      {/* role="status" makes screen readers announce progress and results. */}
      <p className="cc-fb-status" role="status">
        {analyzing && "Reading your resume and asking the AI. This usually takes 10 to 30 seconds."}
        {!analyzing && notice}
      </p>

      {error && (
        <p className="cc-error" role="alert">
          {error}
        </p>
      )}

      {feedback === undefined && <p className="cc-muted">Loading…</p>}

      {feedback === null && !analyzing && !error && (
        <p className="cc-muted">
          This resume hasn't been reviewed yet. Get AI suggestions on wording, impact and missing skills.
        </p>
      )}

      {/* ---------------- The review ---------------- */}
      {hasReview && (
        <div className={`cc-fb-review ${analyzing ? "is-busy" : ""}`}>
          {feedback.is_outdated && (
            <p className="cc-fb-warning" role="note">
              You replaced this resume after this review. Analyze again for up-to-date feedback.
            </p>
          )}

          <div className="cc-fb-overview">
            <div className={`cc-fb-score is-${scoreBand(feedback.overall_score)}`}>
              <span className="cc-fb-score-num">{feedback.overall_score}</span>
              <span className="cc-fb-score-max">/100</span>
            </div>
            <div className="cc-fb-overview-text">
              <p className="cc-fb-score-label">{scoreLabel(feedback.overall_score)}</p>
              <p className="cc-fb-summary">{feedback.summary}</p>
              <p className="cc-fb-meta">
                Reviewed {formatDate(feedback.created_at)}
                {feedback.job_id &&
                  (tailoredJob ? ` for ${tailoredJob.title} at ${tailoredJob.company}` : " for a job posting")}
              </p>
            </div>
          </div>

          {feedback.strengths.length > 0 && (
            <div className="cc-fb-block">
              <h3 className="cc-fb-h3">What works well</h3>
              <ul className="cc-fb-strengths">
                {feedback.strengths.map((strength) => (
                  <li key={strength}>{strength}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="cc-fb-block">
            <h3 className="cc-fb-h3">Suggestions ({feedback.suggestions.length})</h3>
            <ul className="cc-fb-list">
              {feedback.suggestions.map((s) => {
                const decision = decisions[s.id];
                return (
                  <li key={s.id} className={`cc-fb-item ${decision ? `is-${decision}` : ""}`}>
                    <div className="cc-fb-tags">
                      <span className={`cc-fb-tag is-${s.priority}`}>{PRIORITY_LABEL[s.priority]}</span>
                      <span className="cc-fb-tag">{CATEGORY_LABEL[s.category]}</span>
                      {/* Skip the section when it just repeats the category ("Skills"). */}
                      {s.section.toLowerCase() !== CATEGORY_LABEL[s.category].toLowerCase() && (
                        <span className="cc-fb-tag">{s.section}</span>
                      )}
                      {decision && (
                        <span className={`cc-fb-tag ${decision === "accepted" ? "is-decision" : ""}`}>
                          {decision === "accepted" ? "Accepted" : "Dismissed"}
                        </span>
                      )}
                    </div>

                    {decision !== "dismissed" && (
                      <>
                        {s.original ? (
                          <div className="cc-fb-change">
                            <p className="cc-fb-before">
                              <span className="cc-fb-change-label">Current</span>
                              {s.original}
                            </p>
                            <p className="cc-fb-after">
                              <span className="cc-fb-change-label">Suggested</span>
                              {s.suggested}
                            </p>
                          </div>
                        ) : (
                          <p className="cc-fb-after">
                            <span className="cc-fb-change-label">Add</span>
                            {s.suggested}
                          </p>
                        )}
                        <p className="cc-fb-reason">{s.reason}</p>
                        {s.original && !s.can_apply && (
                          <p className="cc-fb-hint">
                            The AI reworded this line, so it may not match your resume exactly.
                          </p>
                        )}
                      </>
                    )}

                    <div className="cc-fb-actions">
                      {decision ? (
                        <button type="button" className="cc-link" onClick={() => decide(s.id, null)}>
                          Undo
                        </button>
                      ) : (
                        <>
                          <button type="button" className="cc-link" onClick={() => decide(s.id, "accepted")}>
                            Accept
                          </button>
                          <button type="button" className="cc-link" onClick={() => decide(s.id, "dismissed")}>
                            Dismiss
                          </button>
                          <button
                            type="button"
                            className="cc-link"
                            onClick={() => copyText(s.suggested, "Suggestion copied to the clipboard.")}
                          >
                            Copy
                          </button>
                        </>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="cc-fb-footer">
            <p className="cc-muted">
              {accepted.length} of {feedback.suggestions.length} suggestions accepted
            </p>
            <button
              type="button"
              className="cc-upload-btn cc-btn-secondary"
              disabled={accepted.length === 0}
              onClick={() =>
                copyText(acceptedChangesText(accepted), "Accepted changes copied. Paste them into your resume.")
              }
            >
              Copy accepted changes
            </button>
          </div>

          <p className="cc-fb-disclaimer">
            Suggestions are generated by AI ({feedback.model}) and can be wrong. Check every change, and
            replace placeholders like [X%] with your real numbers.
          </p>
        </div>
      )}
    </section>
  );
}
