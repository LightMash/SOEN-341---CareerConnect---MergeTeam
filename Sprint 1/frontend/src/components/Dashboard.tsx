import { useRef, useState } from "react";
import type { DragEvent } from "react";
import type { User } from "../api";

const MAX_SIZE_MB = 5;
const ALLOWED_TYPES = ["pdf", "docx"];

// same fields as ResumeOut in the backend
interface Resume {
  id: number;
  filename: string;
  uploaded_at: string;
  thumbnail_url?: string | null;
}

interface DashboardProps {
  user: User;
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

export default function Dashboard({ user, onLogout }: DashboardProps) {
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

  // only kept in the browser for now, resets on refresh
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function openPicker() {
    inputRef.current?.click();
  }

  function addFile(file: File | undefined) {
    if (!file) return;

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

    // TODO: send the file to the backend (POST /api/resume/upload)
    // and use the resume it returns instead of this one
    const resume: Resume = {
      id: Date.now(),
      filename: file.name,
      uploaded_at: new Date().toISOString(),
    };
    setResumes((prev) => [resume, ...prev]);
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
            <button type="button" className="cc-upload-btn" onClick={openPicker}>
              Upload resume
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
              className={`cc-drop ${dragging ? "is-dragging" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              Drop a resume here or{" "}
              <button type="button" className="cc-link" onClick={openPicker}>
                browse your files
              </button>
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
                    {r.thumbnail_url ? <img src={r.thumbnail_url} alt="" /> : <SheetSketch />}
                  </div>
                  <p className="cc-card-name" title={r.filename}>
                    {r.filename}
                  </p>
                  <p className="cc-card-meta">
                    {fileType(r.filename)}, added {formatDate(r.uploaded_at)}
                  </p>
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
