import { useEffect, useId, useState } from "react";
import type { FormEvent } from "react";
import { listMyResumes } from "../../api";
import type { Resume } from "../../api";
import { CATEGORY_LABELS, createCustomQualification, extractFromResume, getReviewerStatus } from "./matchingApi";
import type { Candidate, Category, ExtractResult, QualificationSource, UnresolvedItem } from "./matchingApi";

// "Import from resume": scans a PDF and shows a checklist of what was found.
// Nothing is saved until the seeker presses "Add selected".

const STATE_NOTES: Record<Candidate["state"], string | null> = {
  found: null,
  in_progress: "In progress — not counted until completed",
  questionable: "Flagged by the second-pass review",
  suggested: "Suggested by the second-pass review",
};

interface ResumeImportProps {
  token: string;
  onCancel: () => void;
  onConfirm: (chosen: { key: string; source: QualificationSource }[]) => Promise<void>;
}

export default function ResumeImport({ token, onCancel, onConfirm }: ResumeImportProps) {
  const fileId = useId();
  const [reviewerEnabled, setReviewerEnabled] = useState(false);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [resumeId, setResumeId] = useState<number | "">("");
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [added, setAdded] = useState<Candidate[]>([]); // "add as new" items created here
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getReviewerStatus(token)
      .then((s) => setReviewerEnabled(s.enabled))
      .catch(() => setReviewerEnabled(false));
    listMyResumes(token)
      .then((list) => setResumes(list.filter((r) => r.filename.toLowerCase().endsWith(".pdf"))))
      .catch(() => setResumes([]));
  }, [token]);

  async function scan(e: FormEvent) {
    e.preventDefault();
    const source = file ?? (resumeId === "" ? null : resumeId);
    if (source === null) {
      setError("Choose a PDF file or one of your saved resumes.");
      return;
    }
    setScanning(true);
    setError("");
    try {
      const data = await extractFromResume(source, token);
      setResult(data);
      setAdded([]);
      // Only plain "found" items start checked; everything else needs a decision.
      setChecked(new Set(data.candidates.filter((c) => c.state === "found" && !c.already_added).map((c) => c.key)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't scan the resume. Try again.");
    } finally {
      setScanning(false);
    }
  }

  function toggle(key: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function addAsNew(item: UnresolvedItem) {
    setError("");
    try {
      const category: Category = item.category ?? "skill";
      const name = item.field ? `${item.name} — ${item.field}` : item.name;
      const created = await createCustomQualification(category, name, token);
      setAdded((prev) => [
        ...prev,
        { ...created, source: "reviewer", state: "suggested", reason: null, snippet: "", already_added: false },
      ]);
      setChecked((prev) => new Set(prev).add(created.key));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add it. Try again.");
    }
  }

  async function confirm() {
    if (!result) return;
    const all = [...result.candidates, ...added];
    const chosen = all
      .filter((c) => checked.has(c.key) && !c.already_added)
      .map((c) => ({
        key: c.key,
        source: (c.source === "reviewer" ? "reviewer_suggestion" : "resume_scan") as QualificationSource,
      }));
    setSaving(true);
    try {
      await onConfirm(chosen);
    } finally {
      setSaving(false);
    }
  }

  const candidates = result ? [...result.candidates, ...added] : [];
  const addedNames = new Set(added.map((a) => a.name));
  const unresolved = (result?.unresolved ?? []).filter(
    (u) => !addedNames.has(u.field ? `${u.name} — ${u.field}` : u.name)
  );

  return (
    <div className="cc-import" role="region" aria-label="Import qualifications from a resume">
      <h3 className="cc-subhead">Import from resume</h3>

      {reviewerEnabled && (
        <p className="cc-import-notice" role="note">
          When you scan, your resume text is also sent to an external service for a second-pass review.
        </p>
      )}

      {!result && (
        <form className="cc-import-form" onSubmit={scan}>
          <label htmlFor={fileId}>PDF resume</label>
          <input
            id={fileId}
            type="file"
            accept="application/pdf,.pdf"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setResumeId("");
            }}
          />
          {resumes.length > 0 && (
            <label>
              Or use a saved resume{" "}
              <select
                className="cc-input"
                value={resumeId}
                onChange={(e) => {
                  setResumeId(e.target.value === "" ? "" : Number(e.target.value));
                  setFile(null);
                }}
              >
                <option value="">Choose…</option>
                {resumes.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.filename}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="cc-form-actions">
            <button type="submit" className="cc-upload-btn" disabled={scanning}>
              {scanning ? "Scanning…" : "Scan resume"}
            </button>
            <button type="button" className="cc-upload-btn cc-btn-secondary" onClick={onCancel}>
              Cancel
            </button>
          </div>
        </form>
      )}

      {error && (
        <p className="cc-error" role="alert">
          {error}
        </p>
      )}

      {result && (
        <>
          {result.message && <p className="cc-muted">{result.message}</p>}
          {candidates.length > 0 && (
            <ul className="cc-import-list">
              {candidates.map((c) => {
                const note = STATE_NOTES[c.state];
                return (
                  <li key={c.key} className={`cc-import-item cc-import-item--${c.state}`}>
                    <label>
                      <input
                        type="checkbox"
                        checked={c.already_added || checked.has(c.key)}
                        disabled={c.already_added}
                        onChange={() => toggle(c.key)}
                      />{" "}
                      <strong>{c.name}</strong>{" "}
                      <span className="cc-muted">{CATEGORY_LABELS[c.category]}</span>
                    </label>
                    {c.already_added && <span className="cc-import-note">Already on your profile</span>}
                    {note && <span className="cc-import-note">{note}</span>}
                    {c.state === "questionable" && c.reason && (
                      <span className="cc-import-note">Reason: {c.reason}</span>
                    )}
                    {c.snippet && <span className="cc-import-snippet">“{c.snippet}”</span>}
                  </li>
                );
              })}
            </ul>
          )}

          {unresolved.length > 0 && (
            <div>
              <p className="cc-muted">The second-pass review also mentioned these, which aren't in the standard list:</p>
              <ul className="cc-import-list">
                {unresolved.map((u) => (
                  <li key={`${u.category}-${u.name}-${u.field}`} className="cc-import-item">
                    <span>
                      {u.name}
                      {u.field ? ` — ${u.field}` : ""}
                    </span>
                    <button type="button" className="cc-upload-btn cc-btn-secondary" onClick={() => addAsNew(u)}>
                      Add as new
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="cc-form-actions">
            <button type="button" className="cc-upload-btn" onClick={confirm} disabled={saving || checked.size === 0}>
              {saving ? "Saving…" : `Add selected (${checked.size})`}
            </button>
            <button type="button" className="cc-upload-btn cc-btn-secondary" onClick={onCancel} disabled={saving}>
              Cancel
            </button>
          </div>
        </>
      )}
    </div>
  );
}
