import { useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import type { Certification, StudyChat } from "../studyPartnerApi";
import {
  MAX_MESSAGE_LENGTH,
  getCertifications,
  getStudyChat,
  resetStudyChat,
  sendStudyMessage,
} from "../studyPartnerApi";
import "../styles/studyPartner.css";

// HOW TO USE (see JobDashboardTab.tsx)
//
//   <StudyPartnerPanel job={job} token={token} onClose={() => setStudyJob(null)} />
//
// Render it for job seekers only (the backend answers 403 to recruiters).
// It loads the saved chat and the suggested certifications when it appears,
// so give it a `key={job.id}` to start fresh for another job.

interface StudyPartnerPanelProps {
  job: { id: number; title: string; company: string };
  token: string;
  onClose: () => void;
}

export default function StudyPartnerPanel({ job, token, onClose }: StudyPartnerPanelProps) {
  const [chat, setChat] = useState<StudyChat | null>(null);
  const [certs, setCerts] = useState<Certification[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [draft, setDraft] = useState("");
  // The question being answered right now. It is shown at once, before the
  // server has saved it, so the chat feels instant.
  const [pending, setPending] = useState<string | null>(null);
  const [sendError, setSendError] = useState("");
  const [confirmReset, setConfirmReset] = useState(false);

  const panelRef = useRef<HTMLElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  // A ref as well as state: state only updates on the next render, so a fast
  // double click could still start two requests.
  const busyRef = useRef(false);

  // Load the saved conversation and the certifications ONCE per job. `cancelled`
  // drops the answers if the panel closes or the job changes meanwhile.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError("");

    getStudyChat(job.id, token)
      .then((data) => {
        if (!cancelled) setChat(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setLoadError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    // The certifications are a bonus: if they fail, the chat still works.
    getCertifications(job.id, token)
      .then((data) => {
        if (!cancelled) setCerts(data);
      })
      .catch(() => {
        if (!cancelled) setCerts([]);
      });

    return () => {
      cancelled = true;
    };
  }, [job.id, token]);

  // Bring the panel into view when it opens (the job list is long).
  useEffect(() => {
    panelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  // Keep the newest message in view.
  const messageCount = chat?.messages.length ?? 0;
  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [messageCount, pending]);

  const messages = chat?.messages ?? [];
  const lastMessage = messages[messages.length - 1];
  // Follow-up chips belong to the latest answer only.
  const followUps =
    lastMessage?.role === "assistant" ? lastMessage.suggested_questions : [];
  const chips = messages.length === 0 ? (chat?.starter_questions ?? []) : followUps;
  const sending = pending !== null;
  const trimmed = draft.trim();

  async function send(text: string) {
    const clean = text.trim();
    if (!clean || busyRef.current) return;
    busyRef.current = true;
    setSendError("");
    setPending(clean);
    setDraft("");
    try {
      setChat(await sendStudyMessage(job.id, clean, token));
    } catch (err) {
      // Nothing was saved, so give the text back to retry or edit.
      setDraft(clean);
      setSendError((err as Error).message);
    } finally {
      busyRef.current = false;
      setPending(null);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void send(draft);
  }

  // Enter sends, Shift+Enter adds a line.
  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send(draft);
    }
  }

  async function handleReset() {
    setConfirmReset(false);
    setSendError("");
    try {
      await resetStudyChat(job.id, token);
      setChat(await getStudyChat(job.id, token));
    } catch (err) {
      setSendError((err as Error).message);
    }
  }

  return (
    <section
      className="cc-section cc-sp"
      ref={panelRef}
      id={`study-partner-${job.id}`}
      aria-labelledby={`study-partner-title-${job.id}`}
    >
      <div className="cc-sp-head">
        <div>
          <h2 className="cc-section-title" id={`study-partner-title-${job.id}`}>
            Study partner
          </h2>
          <p className="cc-subtitle">
            {job.title} at {job.company}
          </p>
        </div>
        <div className="cc-sp-head-actions">
          <button
            type="button"
            className="cc-link"
            onClick={() => setConfirmReset(true)}
            disabled={messages.length === 0 || sending}
          >
            Start over
          </button>
          <button type="button" className="cc-link" onClick={onClose}>
            Close
          </button>
        </div>
      </div>

      {confirmReset && (
        <div className="cc-sp-confirm" role="alertdialog" aria-label="Confirm start over">
          <span>Delete this conversation and start again?</span>
          <button type="button" className="cc-upload-btn" onClick={handleReset} autoFocus>
            Delete
          </button>
          <button
            type="button"
            className="cc-upload-btn cc-btn-secondary"
            onClick={() => setConfirmReset(false)}
          >
            Keep it
          </button>
        </div>
      )}

      {loading && <p className="cc-muted">Loading your chat…</p>}
      {!loading && loadError && (
        <p className="cc-error" role="alert">
          {loadError}
        </p>
      )}

      {!loading && !loadError && (
        <>
          {messages.length === 0 && !sending && (
            <p className="cc-sp-intro">
              Ask anything about this role. I only use this posting, so I won&apos;t guess company
              facts.
            </p>
          )}

          {(messages.length > 0 || sending) && (
            <div className="cc-sp-log" ref={logRef} role="log" aria-live="polite" aria-label="Conversation">
              {messages.map((m) => (
                <div key={m.id} className={`cc-sp-msg ${m.role === "user" ? "is-user" : "is-ai"}`}>
                  <span className="cc-sp-who">{m.role === "user" ? "You" : "Study partner"}</span>
                  {m.text}
                </div>
              ))}
              {pending !== null && (
                <>
                  <div className="cc-sp-msg is-user">
                    <span className="cc-sp-who">You</span>
                    {pending}
                  </div>
                  <div className="cc-sp-msg is-ai" aria-hidden="true">
                    <span className="cc-sp-dots">
                      <span />
                      <span />
                      <span />
                    </span>
                  </div>
                </>
              )}
            </div>
          )}

          {chips.length > 0 && (
            <div className="cc-sp-chips" aria-label="Suggested questions">
              {chips.map((q) => (
                <button
                  key={q}
                  type="button"
                  className="cc-sp-chip"
                  disabled={sending}
                  onClick={() => void send(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          <p className="cc-sp-status" role="status">
            {sending ? "Thinking… this usually takes a few seconds." : ""}
          </p>
          {sendError && (
            <p className="cc-error" role="alert">
              {sendError}
            </p>
          )}

          <form className="cc-sp-compose" onSubmit={handleSubmit}>
            <label className="cc-sp-label" htmlFor={`study-input-${job.id}`}>
              Your question
            </label>
            <div className="cc-sp-row">
              <textarea
                id={`study-input-${job.id}`}
                className="cc-sp-input"
                rows={2}
                maxLength={MAX_MESSAGE_LENGTH}
                placeholder="Type a question. Enter sends, Shift+Enter adds a line."
                value={draft}
                disabled={sending}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={handleKeyDown}
              />
              <button type="submit" className="cc-upload-btn" disabled={sending || !trimmed}>
                Send
              </button>
            </div>
            <p className={`cc-sp-count${draft.length > MAX_MESSAGE_LENGTH * 0.9 ? " is-over" : ""}`}>
              {draft.length} / {MAX_MESSAGE_LENGTH}
            </p>
          </form>

          {certs.length > 0 && (
            <details className="cc-sp-certs" open>
              <summary>Useful certifications</summary>
              <p className="cc-sp-certs-note">
                Picked for the skills in this posting. Links go to the official pages, where the
                issuer sets fees and exam details.
              </p>
              <ul className="cc-sp-certlist">
                {certs.map((c) => (
                  <li key={c.id} className="cc-sp-cert">
                    <div className="cc-sp-cert-tags">
                      <span className="cc-sp-tag">{c.level}</span>
                      <span className="cc-sp-tag is-match">Matches: {c.topic}</span>
                    </div>
                    <h4>{c.name}</h4>
                    <p>
                      {c.issuer}. {c.summary}
                    </p>
                    <a href={c.url} target="_blank" rel="noopener noreferrer">
                      View certification
                      <span className="cc-visually-hidden"> (opens in a new tab)</span> ↗
                    </a>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}

      <p className="cc-sp-disclaimer">
        Answers are generated by AI and can be wrong. Your chat for this job is saved to your account.
      </p>
    </section>
  );
}
