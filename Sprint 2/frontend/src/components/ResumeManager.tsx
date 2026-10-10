import { useEffect, useRef, useState } from "react";
import type { DragEvent } from "react";
import type { Resume } from "../api";
import {
  uploadResume,
  listMyResumes,
  deleteResume,
  downloadResume,
  replaceResume,
  setPrimaryResume,
} from "../api";

// Everything resume-related lives here. This logic used to be inside
// Dashboard.tsx; it moved so the Profile tab can render it and Dashboard.tsx
// could become a thin shell. Upload, list, delete and download behave exactly
// as before — Sprint 2 adds Replace, Set primary, a "Primary" badge and a
// delete confirmation.

const MAX_SIZE_MB = 5;
const ALLOWED_TYPES = ["pdf", "docx"];

interface ResumeManagerProps {
  // The user's JWT. Every resume endpoint is protected by
  // `Depends(get_current_user)` on the backend, so every call carries it.
  token: string;
  // Called after the NUMBER of resumes changes (upload / delete). The
  // Profile tab uses it to refresh its completeness bar, because "has a
  // resume" is one of the checks that bar is made of.
  onChange?: () => void;
}

function fileType(filename: string) {
  return filename.split(".").pop()?.toUpperCase() || "FILE";
}

function formatDate(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// placeholder until we have real thumbnails
function SheetSketch() {
  return (
    <div className="cc-sketch" aria-hidden="true">
      <span className="cc-sketch-name" />
      <span className="cc-sketch-role" />
      <span className="cc-sketch-line" />
      <span className="cc-sketch-line" />
      <span className="cc-sketch-line is-short" />
      <span className="cc-sketch-line is-gap" />
      <span className="cc-sketch-line is-shorter" />
    </div>
  );
}

// Client-side pre-checks shared by upload AND replace. Catches obviously
// wrong files (wrong extension, too large) instantly, without a network
// request. This is purely a fast-feedback UX shortcut — the backend enforces
// the real rules independently (MIME type + the same 5MB limit), so a file
// that slips past this still cannot be stored unless it is genuinely valid.
// Returns "" when the file is fine, otherwise the message to show.
function validateFile(file: File): string {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!ALLOWED_TYPES.includes(ext)) return "Only PDF or DOCX files can be uploaded.";
  if (file.size > MAX_SIZE_MB * 1024 * 1024) {
    return `That file is over ${MAX_SIZE_MB} MB. Try a smaller version.`;
  }
  return "";
}

export default function ResumeManager({ token, onChange }: ResumeManagerProps) {
  // Resumes live on the server (Postgres + disk), so this state is a
  // client-side CACHE of what the backend has, not the source of truth. It is
  // filled by the fetch-on-mount effect below and kept in sync by using the
  // objects the backend returns rather than guessing the new state locally.
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  // True while an upload/replace is in flight, so the buttons and drop zone
  // are disabled and a second request can't start before the first finishes.
  const [uploading, setUploading] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  // "Replace" uses its own hidden file input, separate from the upload one.
  // A file input can't carry extra data, so this ref remembers WHICH resume
  // the user clicked "Replace" on until they finish picking a file. (A ref,
  // not state: changing it must not trigger a re-render.)
  const replaceInputRef = useRef<HTMLInputElement>(null);
  const replaceTargetRef = useRef<number | null>(null);

  // Fetch-on-mount: load whatever resumes this user already has
  // (GET /api/resume/mine), so resumes uploaded in an earlier session show up
  // right away instead of only after a fresh upload.
  useEffect(() => {
    listMyResumes(token)
      .then(setResumes)
      .catch(() => setError("Couldn't load your resumes. Try refreshing the page."));
  }, [token]);

  function openPicker() {
    inputRef.current?.click();
  }

  function openReplacePicker(id: number) {
    replaceTargetRef.current = id;
    replaceInputRef.current?.click();
  }

  async function addFile(file: File | undefined) {
    if (!file) return;

    const problem = validateFile(file);
    if (problem) {
      setError(problem);
      return;
    }

    setError("");
    setUploading(true);
    try {
      // `resume` is the real database row the backend just created: real id,
      // the server's own upload timestamp, and is_primary=true if this is the
      // user's first resume. Using it (instead of building a fake local entry)
      // means what's on screen always matches what's actually stored.
      const { resume } = await uploadResume(file, token);
      setResumes((prev) => [resume, ...prev]);
      onChange?.();
    } catch (err) {
      // The backend's own message already explains what was wrong
      // (wrong content-type, too large, ...), so show it directly.
      setError(err instanceof Error ? err.message : "Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  }

  // Replace the file behind an existing resume (PUT /api/resume/{id}). The
  // card keeps its position and its primary status; the backend returns the
  // updated row, which we swap in place of the old one.
  async function replaceFile(id: number, file: File | undefined) {
    if (!file) return;

    const problem = validateFile(file);
    if (problem) {
      setError(problem);
      return;
    }

    setError("");
    setUploading(true);
    try {
      const { resume } = await replaceResume(id, file, token);
      setResumes((prev) => prev.map((r) => (r.id === id ? resume : r)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't replace that resume.");
    } finally {
      setUploading(false);
    }
  }

  async function handleSetPrimary(id: number) {
    try {
      await setPrimaryResume(id, token);
      // Only one resume is primary at a time, and the backend just enforced
      // that — mirror it locally without another round trip.
      setResumes((prev) => prev.map((r) => ({ ...r, is_primary: r.id === id })));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't set that resume as primary.");
    }
  }

  // Calls the backend first (DELETE /api/resume/{id}, which also verifies the
  // resume belongs to this user) and only updates the screen once that
  // succeeds, so a failed request leaves the card visible.
  async function handleDelete(id: number) {
    // Deleting is permanent (the file is removed from disk), so confirm first.
    if (!window.confirm("Delete this resume? This can't be undone.")) return;

    try {
      await deleteResume(id, token);
      // Re-fetch instead of filtering locally: if the deleted resume was the
      // primary one, the backend promotes the newest remaining resume, and
      // the list has to show that change too.
      setResumes(await listMyResumes(token));
      onChange?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't delete that resume.");
    }
  }

  // downloadResume() fetches the raw bytes with the auth header attached (a
  // plain <a href> can't send an Authorization header) and then triggers the
  // browser's normal "Save As" flow.
  async function handleDownload(id: number, filename: string) {
    try {
      await downloadResume(id, filename, token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't download that resume.");
    }
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    addFile(e.dataTransfer.files[0]);
  }

  function handleDragLeave(e: DragEvent<HTMLDivElement>) {
    // dragleave also fires when the pointer moves over child elements; only
    // clear the highlight when it truly leaves the drop zone.
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
      setDragging(false);
    }
  }

  return (
    <section className="cc-section" aria-label="Resumes">
      <div className="cc-section-head">
        <div>
          <h2 className="cc-section-title">Resumes</h2>
          <p className="cc-subtitle">PDF or DOCX, up to {MAX_SIZE_MB} MB</p>
        </div>

        <button type="button" className="cc-upload-btn" onClick={openPicker} disabled={uploading}>
          {uploading ? "Uploading..." : "Upload resume"}
        </button>
      </div>

      {/* Two hidden file inputs: one for new uploads, one for "Replace". */}
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx"
        className="cc-visually-hidden"
        tabIndex={-1}
        onChange={(e) => {
          addFile(e.target.files?.[0]);
          e.target.value = ""; // so the same file can be picked again
        }}
      />

      <input
        ref={replaceInputRef}
        type="file"
        accept=".pdf,.docx"
        className="cc-visually-hidden"
        tabIndex={-1}
        onChange={(e) => {
          const id = replaceTargetRef.current;
          const file = e.target.files?.[0];
          e.target.value = ""; // allow re-picking the same file next time
          replaceTargetRef.current = null;
          if (id !== null) replaceFile(id, file);
        }}
      />

      <div
        // `is-uploading` lets index.css dim the drop zone while a request is
        // in flight, same idea as the disabled button above.
        className={`cc-drop ${dragging ? "is-dragging" : ""} ${uploading ? "is-uploading" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!uploading) setDragging(true);
        }}
        onDragLeave={handleDragLeave}
        onDrop={uploading ? (e) => e.preventDefault() : handleDrop}
      >
        {uploading ? (
          "Uploading..."
        ) : (
          <>
            Drop a resume here or{" "}
            <button type="button" className="cc-link" onClick={openPicker}>
              browse your files
            </button>
          </>
        )}
      </div>

      {error && (
        <p className="cc-error" role="alert">
          {error}
        </p>
      )}

      {resumes.length === 0 && (
        <p className="cc-muted">No resumes yet. Upload your first one to get started.</p>
      )}

      <ul className="cc-grid">
        {resumes.map((r) => (
          <li key={r.id} className="cc-card">
            <div className="cc-thumb">
              {/* The backend doesn't generate real thumbnails yet (ResumeOut
                  has no thumbnail field), so this is always the placeholder. */}
              <SheetSketch />
              {r.is_primary && <span className="cc-badge">Primary</span>}
            </div>
            <p className="cc-card-name" title={r.filename}>
              {r.filename}
            </p>
            <p className="cc-card-meta">
              {fileType(r.filename)}, added {formatDate(r.uploaded_at)}
            </p>
            <div className="cc-card-actions">
              <button type="button" className="cc-link" onClick={() => handleDownload(r.id, r.filename)}>
                Download
              </button>
              <button
                type="button"
                className="cc-link"
                onClick={() => openReplacePicker(r.id)}
                disabled={uploading}
              >
                Replace
              </button>
              {/* Already-primary resumes don't need the button. */}
              {!r.is_primary && (
                <button type="button" className="cc-link" onClick={() => handleSetPrimary(r.id)}>
                  Set primary
                </button>
              )}
              <button type="button" className="cc-link cc-link-danger" onClick={() => handleDelete(r.id)}>
                Delete
              </button>
            </div>
          </li>
        ))}

        <li>
          <button type="button" className="cc-add" onClick={openPicker} aria-label="Upload a resume">
            <span aria-hidden="true">+</span>
          </button>
        </li>
      </ul>
    </section>
  );
}
