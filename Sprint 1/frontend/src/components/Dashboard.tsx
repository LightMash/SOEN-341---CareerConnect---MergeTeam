import { useEffect, useRef, useState } from "react";
import type { DragEvent } from "react";
import type { User, Resume } from "../api";
import { uploadResume, listMyResumes, deleteResume, downloadResume } from "../api";

// NOTE: we no longer declare our own local `Resume` interface here — we
// import the one already defined in api.ts (which mirrors the backend's
// ResumeOut schema exactly: id, user_id, filename, uploaded_at). Keeping a
// second, hand-copied interface in this file risked drifting out of sync
// with the real shape the backend actually returns (it was already missing
// `user_id`). One shared type, defined once, used everywhere.

const MAX_SIZE_MB = 5;
const ALLOWED_TYPES = ["pdf", "docx"];

interface DashboardProps {
  user: User;
  // The logged-in user's JWT (from App.tsx's `token` state). Every resume
  // endpoint on the backend (upload/list/delete/download) is protected by
  // `Depends(get_current_user)`, which reads this token from the
  // `Authorization: Bearer <token>` header — so every call this component
  // makes to the resume API has to carry it.
  token: string;
  onLogout: () => void;
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

export default function Dashboard({ user, token, onLogout }: DashboardProps) {
  const isSeeker = user.role === "job_seeker";

  const initials =
    user.full_name
      .trim()
      .split(/\s+/)
      .map((part) => part.charAt(0))
      .join("")
      .slice(0, 2)
      .toUpperCase() || "?";
  const roleLabel = isSeeker ? "Job seeker" : "Recruiter";

  // Resumes now live on the server (backend/routers/resume.py persists them
  // to Postgres + disk), so this state is a client-side CACHE of what the
  // backend has, not the source of truth. It starts empty and gets filled by
  // the fetch-on-mount effect below, and is kept in sync with the server on
  // every upload/delete by using the response the backend actually returns
  // rather than guessing at the new state ourselves.
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  // True while an upload is in flight, so we can disable the drop
  // zone/button and avoid firing a second upload before the first finishes.
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch-on-mount: load whatever resumes this user has already uploaded
  // (in an earlier session, or before this page refreshed) via
  // GET /api/resume/mine. Without this, a real, already-saved resume would
  // never appear until the user re-uploaded it — the old version of this
  // component never asked the backend for anything, so its `resumes` state
  // was always empty on every fresh page load. `token` is in the dependency
  // array on principle (if it ever changed — e.g. a future token refresh —
  // we'd want to refetch with the new one), even though in practice it's
  // set once per login and doesn't change while this component is mounted.
  useEffect(() => {
    // Recruiters don't have a resume list UI at all (see the role branch in
    // the JSX below), so there's no reason to hit this endpoint for them.
    if (!isSeeker) return;

    listMyResumes(token)
      .then(setResumes)
      .catch(() => setError("Couldn't load your resumes. Try refreshing the page."));
  }, [isSeeker, token]);

  function openPicker() {
    inputRef.current?.click();
  }

  // `async` now, since it has to wait on the network request to the backend
  // before it knows whether the upload actually succeeded. Both callers
  // (handleDrop and the hidden <input>'s onChange) call this without
  // `await`, which is fine — they don't need to block on the result, the
  // state updates inside this function are what drive the UI once it
  // resolves.
  async function addFile(file: File | undefined) {
    if (!file) return;

    // Client-side pre-checks: catch obviously-wrong files (wrong extension,
    // too large) immediately, without even making a network request. This
    // is purely a fast-feedback UX shortcut — the backend enforces the real
    // rules independently (by MIME type via `file.content_type`, and the
    // same 5MB limit via MAX_UPLOAD_MB in routers/resume.py), so a file that
    // somehow slips past this check still can't reach the database unless
    // it's genuinely valid.
    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!ALLOWED_TYPES.includes(ext)) {
      setError("Only PDF or DOCX files can be uploaded.");
      return;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`That file is over ${MAX_SIZE_MB} MB. Try a smaller version.`);
      return;
    }

    setError("");
    setUploading(true);
    try {
      // uploadResume() (api.ts) sends the file as multipart/form-data to
      // POST /api/resume/upload with the Authorization header set, and
      // resolves with { message, resume } — `resume` is the real database
      // row FastAPI just created (real `id`, real `user_id`, and
      // `uploaded_at` as the server's own clock recorded it, not the
      // browser's). We use THAT object instead of building a fake one
      // locally, so what's on screen always matches what's actually stored.
      const { resume } = await uploadResume(file, token);
      setResumes((prev) => [resume, ...prev]);
    } catch (err) {
      // uploadResume() throws with the backend's own message when the
      // server rejects the file (wrong content-type, too large, etc.) —
      // surface that message directly rather than a generic one, since it
      // already explains exactly what was wrong.
      setError(err instanceof Error ? err.message : "Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  }

  // Called from each resume card's Delete button. Calls the backend first
  // (DELETE /api/resume/{id}, which also checks the resume actually belongs
  // to this user) and only removes it from local state once that succeeds —
  // so a failed delete (e.g. a network error) leaves the card on screen
  // instead of silently disappearing while still existing on the server.
  async function handleDelete(id: number) {
    try {
      await deleteResume(id, token);
      setResumes((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't delete that resume.");
    }
  }

  // Called from each resume card's Download button. downloadResume()
  // (api.ts) fetches the file's raw bytes with the auth header attached
  // (a plain <a href="..."> can't send an Authorization header, which is
  // why this goes through fetch + a Blob instead of a normal link), then
  // triggers the browser's normal "Save As" flow.
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
    // dragleave also fires when hovering child elements
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
      setDragging(false);
    }
  }

  return (
    <div className="cc-dashboard">
      <aside className="cc-sidebar">
        <div className="cc-brand">
          <span className="cc-brand-first">Career</span>
          <span className="cc-brand-second">Connect</span>
        </div>

        <div className="cc-photo" role="img" aria-label="Profile photo placeholder">
          {initials}
        </div>
        <p className="cc-name">{user.full_name}</p>
        <p className="cc-role">{roleLabel}</p>
        <p className="cc-email">{user.email}</p>

        {/* add more sections here */}
        <nav className="cc-nav" aria-label="Dashboard sections">
          <button type="button" className="cc-nav-item is-active" aria-current="page">
            {isSeeker ? "Resumes" : "Overview"}
          </button>
        </nav>

        <button type="button" className="cc-nav-item cc-logout" onClick={onLogout}>
          Log out
        </button>
      </aside>

      <main className="cc-main">
        <header className="cc-main-head">
          <div>
            <h1 className="cc-title">{isSeeker ? "Resumes" : "Dashboard"}</h1>
            <p className="cc-subtitle">
              {isSeeker
                ? `PDF or DOCX, up to ${MAX_SIZE_MB} MB`
                : "Your recruiter tools will live here."}
            </p>
          </div>

          {isSeeker && (
            <button
              type="button"
              className="cc-upload-btn"
              onClick={openPicker}
              disabled={uploading}
            >
              {uploading ? "Uploading..." : "Upload resume"}
            </button>
          )}
        </header>

        {isSeeker ? (
          <>
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

            <div
              // `is-uploading` lets index.css dim the drop zone visually while
              // a request is in flight, same idea as the button above.
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
                    {/* The backend doesn't generate real thumbnails yet —
                        ResumeOut has no thumbnail_url field — so this always
                        renders the placeholder sketch. If a real thumbnail
                        field is added to the backend later, this is the only
                        line that would need to change (back to an `r.thumbnail_url
                        ? <img ... /> : <SheetSketch />` check). */}
                    <SheetSketch />
                  </div>
                  <p className="cc-card-name" title={r.filename}>
                    {r.filename}
                  </p>
                  <p className="cc-card-meta">
                    {fileType(r.filename)}, added {formatDate(r.uploaded_at)}
                  </p>
                  <div className="cc-card-actions">
                    <button
                      type="button"
                      className="cc-link"
                      onClick={() => handleDownload(r.id, r.filename)}
                    >
                      Download
                    </button>
                    <button
                      type="button"
                      className="cc-link cc-link-danger"
                      onClick={() => handleDelete(r.id)}
                    >
                      Delete
                    </button>
                  </div>
                </li>
              ))}

              <li>
                <button
                  type="button"
                  className="cc-add"
                  onClick={openPicker}
                  aria-label="Upload a resume"
                >
                  <span aria-hidden="true">+</span>
                </button>
              </li>
            </ul>
          </>
        ) : (
          <section className="cc-soon">
            <h2 className="cc-section-title">Recruiter tools are on the way</h2>
            <p>Posting jobs and finding candidates will show up here in a later sprint.</p>
          </section>
        )}
      </main>
    </div>
  );
}
