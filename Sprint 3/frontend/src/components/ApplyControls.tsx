import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import type { ApplicationOut, Resume } from "../api";
import { ApiError, listMyResumes, submitApplication } from "../api";
import "../styles/apply.css";

// HOW TO USE (the job listing doesn't exist on main yet, so this is built to
// be dropped into a listing card the moment it lands)
//
//   <ApplyControls
//     job={job}
//     token={token}
//     alreadyApplied={appliedIds.has(job.id)}
//     onApplied={(a) => setAppliedIds((prev) => new Set(prev).add(a.job_id))}
//   />
//
// Render it for job seekers only, and only on jobs that are open. Two wiring
// steps make that work:
//   1. Dashboard.tsx must pass `token={token}` to <JobDashboardTab> (today
//      that tab only receives `user`), and the tab hands it down to each card.
//   2. The tab calls listMyApplications(token) ONCE per listing view (never
//      once per card), builds `appliedIds` (a Set of job_id) from the result
//      and passes it to the cards as shown above.
//
// Everything before "Confirm" lives in this component's state only. Picking
// a resume is NOT saved anywhere (no API call, no storage); the one thing
// that writes to the server is the Confirm button.

interface ApplyControlsProps {
  // Just the fields this component displays (confirm text, success message),
  // so it works with whatever the listing's own Job type turns out to be.
  job: { id: number; title: string; company: string };
  // The job seeker's JWT, same as ResumeManager: both endpoints used here
  // (GET /api/resume/mine, POST /api/applications) are protected.
  token: string;
  // The listing says so when this user already applied earlier (from
  // GET /api/applications/mine). Renders only the "Applied" state.
  alreadyApplied?: boolean;
  // Lets the listing add this job to its own "applied" set. It is not called
  // for a 409, because that response carries no application to hand back.
  onApplied?: (application: ApplicationOut) => void;
}

export default function ApplyControls({ job, token, alreadyApplied, onApplied }: ApplyControlsProps) {
  // The resumes are fetched the FIRST time the menu opens (most cards are
  // never touched, so loading them for every card would be wasted requests)
  // and then kept for this component's lifetime. null = not loaded yet.
  const [resumes, setResumes] = useState<Resume[] | null>(null);
  const [resumesLoading, setResumesLoading] = useState(false);
  const [resumesError, setResumesError] = useState("");

  // The explicit choice. There is deliberately no preselection, not even the
  // primary resume, so applying always uses a resume the user picked.
  const [selected, setSelected] = useState<Resume | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0); // highlighted option while the menu is open

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  // A ref as well as state: state only updates on the next render, so a fast
  // double click on Confirm could get past a `submitting` check twice. The
  // ref flips immediately. (Same reason ResumeManager keeps refs for things
  // that must not wait for a re-render.)
  const submittingRef = useRef(false);

  const [justApplied, setJustApplied] = useState(false); // applied during this visit
  const [jobClosed, setJobClosed] = useState(false); // the backend said it stopped accepting applications
  const [error, setError] = useState("");
  const [message, setMessage] = useState(""); // success / "already applied" text

  const applied = alreadyApplied || justApplied;

  const rootRef = useRef<HTMLDivElement>(null);
  const selectRef = useRef<HTMLButtonElement>(null);
  const applyRef = useRef<HTMLButtonElement>(null);
  const appliedRef = useRef<HTMLSpanElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const hadConfirmRef = useRef(false);

  // useId keeps the ids unique when the listing renders many cards.
  const uid = useId();
  const listId = `${uid}-list`;
  const hintId = `${uid}-hint`;
  const errorId = `${uid}-error`;
  const dialogTitleId = `${uid}-title`;
  const dialogTextId = `${uid}-text`;
  const optionId = (i: number) => `${uid}-opt-${i}`;

  const needsResume = !selected && !jobClosed;
  const applyDisabled = !selected || submitting || jobClosed;

  // Opens/closes the native <dialog> to match `confirmOpen`. showModal() is
  // what gives us the focus trap, the dimmed backdrop and Esc-to-close for
  // free, with no library. The `.open` checks make it safe to run twice
  // (React StrictMode re-runs effects in development).
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (confirmOpen && !dialog.open) dialog.showModal();
    if (!confirmOpen && dialog.open) dialog.close();
  }, [confirmOpen]);

  // After the dialog closes, put focus back somewhere sensible. This runs in
  // an effect (after React has re-rendered) rather than in the dialog's close
  // handler so it sees the final button states: Apply if it is usable again,
  // the Select button if it isn't, or the "Applied" label after a success
  // (Apply no longer exists then, and focus would otherwise fall to <body>).
  useEffect(() => {
    if (confirmOpen) {
      hadConfirmRef.current = true;
      return;
    }
    if (!hadConfirmRef.current) return;
    hadConfirmRef.current = false;
    const apply = applyRef.current;
    const target = appliedRef.current ?? (apply && !apply.disabled ? apply : selectRef.current);
    target?.focus();
  }, [confirmOpen]);

  // While the menu is open, close it when the user clicks or tabs elsewhere.
  useEffect(() => {
    if (!menuOpen) return;
    function closeIfOutside(e: Event) {
      if (!rootRef.current?.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("pointerdown", closeIfOutside);
    document.addEventListener("focusin", closeIfOutside);
    return () => {
      document.removeEventListener("pointerdown", closeIfOutside);
      document.removeEventListener("focusin", closeIfOutside);
    };
  }, [menuOpen]);

  // Keyboard focus lives INSIDE the open menu: on the list once there are
  // options, otherwise on the menu box itself (so Esc still works while it
  // shows "Loading…" or an error). Re-runs when the menu's content changes,
  // because the element that had focus (e.g. the Retry button) may be gone.
  useEffect(() => {
    if (!menuOpen) return;
    (listRef.current ?? menuRef.current)?.focus();
  }, [menuOpen, resumes, resumesLoading, resumesError]);

  // Keep the highlighted option visible when the list scrolls.
  useEffect(() => {
    if (!menuOpen) return;
    listRef.current?.children[activeIndex]?.scrollIntoView({ block: "nearest" });
  }, [menuOpen, activeIndex, resumes]);

  async function loadResumes() {
    setResumesLoading(true);
    setResumesError("");
    try {
      setResumes(await listMyResumes(token));
    } catch {
      setResumesError("Couldn't load your resumes.");
    } finally {
      setResumesLoading(false);
    }
  }

  function openMenu() {
    // Start the highlight on the current choice (or the first resume).
    const current = resumes?.findIndex((r) => r.id === selected?.id) ?? -1;
    setActiveIndex(current >= 0 ? current : 0);
    setMenuOpen(true);
    if (resumes === null && !resumesLoading) void loadResumes();
  }

  function closeMenu(returnFocus: boolean) {
    setMenuOpen(false);
    if (returnFocus) selectRef.current?.focus();
  }

  function choose(resume: Resume) {
    setSelected(resume);
    setError(""); // a new choice deserves a fresh try
    closeMenu(true);
  }

  function handleTriggerKeyDown(e: KeyboardEvent<HTMLButtonElement>) {
    // Enter and Space already click the button; arrows are the extra shortcut
    // listbox-style menus are expected to have.
    if (!menuOpen && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      e.preventDefault();
      openMenu();
    }
  }

  function handleListKeyDown(e: KeyboardEvent<HTMLUListElement>) {
    if (!resumes || resumes.length === 0) return;
    const last = resumes.length - 1;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, last));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
        break;
      case "Home":
        e.preventDefault();
        setActiveIndex(0);
        break;
      case "End":
        e.preventDefault();
        setActiveIndex(last);
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        choose(resumes[Math.min(activeIndex, last)]);
        break;
    }
  }

  // Esc is handled on the menu box (not the list) so it also works while the
  // box only shows "Loading…" or an error.
  function handleMenuKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      closeMenu(true);
    }
  }

  async function handleConfirm() {
    if (submittingRef.current || !selected) return;
    submittingRef.current = true;
    setSubmitting(true);
    setError("");
    try {
      // `application` is the real row the backend just created, so the
      // listing can trust it instead of guessing what was saved.
      const { application } = await submitApplication(job.id, selected.id, token);
      setMessage(`Application sent to ${job.company}.`);
      setJustApplied(true);
      onApplied?.(application);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // Already applied (e.g. from another tab): that is the state the user
        // wanted, so show it as Applied and pass on the backend's wording.
        setMessage(err.message);
        setJustApplied(true);
      } else if (err instanceof ApiError) {
        setError(err.message);
        // We always send a resume_id, so a 400 can only be the job-closed
        // check (the backend runs it before it looks at the resume). It
        // won't change by retrying, so keep Apply disabled.
        if (err.status === 400) setJobClosed(true);
        // 403/404 can mean the resume was deleted or changed elsewhere: drop
        // the cached list so the next time the menu opens it is fetched fresh.
        if (err.status === 403 || err.status === 404) setResumes(null);
        // Any other status (401 included): the backend's message is shown and
        // the selection is kept. There is no token-refresh flow to try.
      } else {
        // fetch() itself failed (offline, server down): its own message
        // ("Failed to fetch") would mean nothing to the user.
        setError("Couldn't reach the server. Please try again.");
      }
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
      setConfirmOpen(false);
    }
  }

  const describedBy = needsResume ? hintId : jobClosed && error ? errorId : undefined;

  return (
    <div className="cc-apply" ref={rootRef}>
      {applied ? (
        // Non-interactive. tabIndex -1 only lets focus land here after a
        // successful apply, since the Apply button that had it just vanished.
        <span className="cc-apply__applied" ref={appliedRef} tabIndex={-1}>
          <span aria-hidden="true">✓ </span>Applied
        </span>
      ) : (
        <>
          <div className="cc-apply__row">
            <div className="cc-apply__select">
              <button
                type="button"
                ref={selectRef}
                className="cc-apply__btn cc-apply__btn--select"
                aria-haspopup="listbox"
                aria-expanded={menuOpen}
                // The visible label becomes the filename once a resume is
                // chosen, so spell out what the button is for.
                aria-label={selected ? `Selected resume: ${selected.filename}. Change resume` : "Select a resume"}
                disabled={submitting}
                onClick={() => (menuOpen ? closeMenu(false) : openMenu())}
                onKeyDown={handleTriggerKeyDown}
              >
                <span className="cc-apply__label" title={selected?.filename}>
                  {selected ? selected.filename : "Select"}
                </span>
                <span className="cc-apply__caret" aria-hidden="true">▾</span>
              </button>

              {menuOpen && (
                <div className="cc-apply__menu" ref={menuRef} tabIndex={-1} onKeyDown={handleMenuKeyDown}>
                  {resumesLoading && <p className="cc-apply__note" role="status">Loading your resumes…</p>}

                  {!resumesLoading && resumesError && (
                    <div className="cc-apply__note">
                      <p className="cc-error" role="alert">{resumesError}</p>
                      <button type="button" className="cc-apply__retry" onClick={() => void loadResumes()}>
                        Try again
                      </button>
                    </div>
                  )}

                  {!resumesLoading && !resumesError && resumes && resumes.length === 0 && (
                    <p className="cc-apply__note">
                      You don't have any resumes yet. Upload one in your Profile tab.
                    </p>
                  )}

                  {!resumesLoading && !resumesError && resumes && resumes.length > 0 && (
                    // Focus stays on the <ul>; aria-activedescendant tells
                    // screen readers which option is highlighted.
                    <ul
                      id={listId}
                      ref={listRef}
                      className="cc-apply__list"
                      role="listbox"
                      tabIndex={-1}
                      aria-label="Your resumes"
                      aria-activedescendant={optionId(activeIndex)}
                      onKeyDown={handleListKeyDown}
                    >
                      {resumes.map((r, i) => (
                        <li
                          key={r.id}
                          id={optionId(i)}
                          role="option"
                          aria-selected={r.id === selected?.id}
                          className={`cc-apply__option ${i === activeIndex ? "is-active" : ""}`}
                          title={r.filename}
                          onClick={() => choose(r)}
                          onMouseEnter={() => setActiveIndex(i)}
                        >
                          <span className="cc-apply__option-name">{r.filename}</span>
                          {r.is_primary && <span className="cc-apply__tag">Primary</span>}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>

            <button
              type="button"
              ref={applyRef}
              className="cc-apply__btn cc-apply__btn--apply"
              // Native `disabled` (not just styling) so it can't be clicked or
              // tabbed to until a resume has been chosen.
              disabled={applyDisabled}
              aria-describedby={describedBy}
              onClick={() => {
                setError("");
                setConfirmOpen(true);
              }}
            >
              {submitting ? "Applying…" : "Apply"}
            </button>
          </div>

          {needsResume && (
            <p className="cc-apply__hint" id={hintId}>
              Select a resume first
            </p>
          )}
        </>
      )}

      {/* The live regions stay mounted (empty) in every state: screen readers
          only announce changes to a region that already exists. */}
      <p className="cc-apply__msg cc-success" role="status">{message}</p>
      <p className="cc-apply__msg cc-error" role="alert" id={errorId}>{error}</p>

      <dialog
        ref={dialogRef}
        className="cc-apply__dialog"
        aria-labelledby={dialogTitleId}
        aria-describedby={dialogTextId}
        // Esc fires "cancel" then "close". Don't let it dismiss the dialog
        // while the request is in flight, or its result would appear out of
        // nowhere. (Browsers may still close on a second Esc; that is safe,
        // the result then just shows inline.)
        onCancel={(e) => {
          if (submittingRef.current) e.preventDefault();
        }}
        // Esc and Cancel both end up here, so `confirmOpen` stays in sync
        // with what the browser actually did.
        onClose={() => setConfirmOpen(false)}
      >
        {selected && (
          <>
            <h3 className="cc-apply__dialog-title" id={dialogTitleId}>Confirm application</h3>
            <p className="cc-apply__dialog-text" id={dialogTextId}>
              Apply to {job.title} at {job.company} using {selected.filename}?
            </p>
            <div className="cc-apply__dialog-actions">
              <button
                type="button"
                className="cc-apply__btn cc-apply__btn--cancel"
                disabled={submitting}
                onClick={() => setConfirmOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="cc-apply__btn cc-apply__btn--apply"
                disabled={submitting}
                onClick={handleConfirm}
              >
                {submitting ? "Applying…" : "Confirm"}
              </button>
            </div>
          </>
        )}
      </dialog>
    </div>
  );
}
