import { useEffect, useState } from "react";
import type { SubmitEvent, ReactNode } from "react";
import {
  listMyPostings,
  createPosting,
  updatePosting,
  setPostingStatus,
  EMPLOYMENT_LABELS,
  WORK_FROM_LABELS,
} from "../../postingsApi";
import type { JobPosting, JobPostingInput, EmploymentType, WorkFrom } from "../../postingsApi";
import "../../styles/postings.css";

// Recruiter side of the Job dashboard (US-04, Task 4.3): a list of the
// recruiter's own postings plus one form used for both creating and editing.

type FormState = Omit<JobPostingInput, "deadline"> & { deadline: string };
type RequiredField = "title" | "company" | "location" | "description";

const EMPTY_FORM: FormState = {
  title: "",
  company: "",
  location: "",
  category: "",
  employment_type: "full_time",
  work_from: "on_site",
  deadline: "",
  description: "",
};

const REQUIRED: [RequiredField, string][] = [
  ["title", "Enter a job title"],
  ["company", "Enter the company name"],
  ["location", "Enter a location"],
  ["description", "Add a short description"],
];

// Deadlines are plain dates ("2026-11-15"). Adding a time of noon stops the
// date from shifting to the day before in timezones behind UTC.
function formatDeadline(date: string) {
  return new Date(`${date}T12:00:00`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// Open postings first, newest first inside each group.
function sortPostings(list: JobPosting[]) {
  return [...list].sort((a, b) => {
    if (a.status !== b.status) return a.status === "open" ? -1 : 1;
    return b.posted_at.localeCompare(a.posted_at);
  });
}

function Field({ label, error, wide, children }: { label: string; error?: string; wide?: boolean; children: ReactNode }) {
  return (
    <label className={`cc-field ${wide ? "is-wide" : ""}`}>
      <span className="cc-field-label">{label}</span>
      {children}
      {error && <span className="cc-field-error">{error}</span>}
    </label>
  );
}

export default function RecruiterPostings({ token }: { token: string }) {
  const [postings, setPostings] = useState<JobPosting[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  // null = form closed, "new" = creating, a number = editing that posting
  const [editing, setEditing] = useState<"new" | number | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<RequiredField, string>>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const [notice, setNotice] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    listMyPostings(token)
      .then((list) => setPostings(sortPostings(list)))
      .catch(() => setLoadError("Couldn't load your postings. Try refreshing the page."))
      .finally(() => setLoading(false));
  }, [token]);

  const openCount = postings.filter((p) => p.status === "open").length;

  function openNewForm() {
    setEditing("new");
    setForm(EMPTY_FORM);
    setFieldErrors({});
    setSaveError("");
    setNotice("");
  }

  function openEditForm(posting: JobPosting) {
    setEditing(posting.id);
    setForm({
      title: posting.title,
      company: posting.company,
      location: posting.location,
      category: posting.category,
      employment_type: posting.employment_type,
      work_from: posting.work_from,
      deadline: posting.deadline ?? "",
      description: posting.description,
    });
    setFieldErrors({});
    setSaveError("");
    setNotice("");
  }

  function closeForm() {
    setEditing(null);
    setSaveError("");
  }

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (key in fieldErrors) {
      setFieldErrors((prev) => ({ ...prev, [key]: undefined }));
    }
  }

  async function handleSubmit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault();

    const errors: Partial<Record<RequiredField, string>> = {};
    for (const [key, message] of REQUIRED) {
      if (!form[key].trim()) errors[key] = message;
    }
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    const input: JobPostingInput = {
      title: form.title.trim(),
      company: form.company.trim(),
      location: form.location.trim(),
      category: form.category.trim(),
      employment_type: form.employment_type,
      work_from: form.work_from,
      deadline: form.deadline || null,
      description: form.description.trim(),
    };

    setSaving(true);
    setSaveError("");
    try {
      if (editing === "new") {
        const created = await createPosting(input, token);
        setPostings((prev) => sortPostings([created, ...prev]));
        setNotice("Job posted");
      } else if (typeof editing === "number") {
        const updated = await updatePosting(editing, input, token);
        setPostings((prev) => sortPostings(prev.map((p) => (p.id === updated.id ? updated : p))));
        setNotice("Changes saved");
      }
      setEditing(null);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Couldn't save the posting. Try again.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleStatus(posting: JobPosting) {
    const next = posting.status === "open" ? "closed" : "open";
    setBusyId(posting.id);
    setNotice("");
    try {
      const updated = await setPostingStatus(posting.id, next, token);
      setPostings((prev) => sortPostings(prev.map((p) => (p.id === updated.id ? updated : p))));
      setNotice(next === "closed" ? "Posting closed" : "Posting reopened");
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Couldn't update the posting. Try again.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <header className="cc-main-head">
        <div>
          <h1 className="cc-title">Your job postings</h1>
          <p className="cc-subtitle">
            {postings.length > 0
              ? `${openCount} open, ${postings.length - openCount} closed`
              : "Post a job so job seekers can find and apply to it."}
          </p>
        </div>
        {editing === null && (
          <button type="button" className="cc-upload-btn" onClick={openNewForm}>
            New posting
          </button>
        )}
      </header>

      {notice && (
        <p className="cc-success" role="status">
          {notice}
        </p>
      )}

      {editing !== null && (
        <form className="cc-section cc-posting-form" onSubmit={handleSubmit} noValidate>
          <h2 className="cc-section-title">{editing === "new" ? "New posting" : "Edit posting"}</h2>

          <div className="cc-form-grid">
            <Field label="Job title *" error={fieldErrors.title} wide>
              <input
                className="cc-input"
                value={form.title}
                maxLength={120}
                placeholder="Software Engineering Intern"
                aria-invalid={Boolean(fieldErrors.title)}
                onChange={(e) => setField("title", e.target.value)}
                autoFocus
              />
            </Field>
            <Field label="Company *" error={fieldErrors.company}>
              <input
                className="cc-input"
                value={form.company}
                maxLength={120}
                aria-invalid={Boolean(fieldErrors.company)}
                onChange={(e) => setField("company", e.target.value)}
              />
            </Field>
            <Field label="Location *" error={fieldErrors.location}>
              <input
                className="cc-input"
                value={form.location}
                maxLength={120}
                placeholder="Montreal, QC"
                aria-invalid={Boolean(fieldErrors.location)}
                onChange={(e) => setField("location", e.target.value)}
              />
            </Field>
            <Field label="Category">
              <input
                className="cc-input"
                value={form.category}
                maxLength={60}
                placeholder="Software Development"
                onChange={(e) => setField("category", e.target.value)}
              />
            </Field>
            <Field label="Apply by">
              <input
                className="cc-input"
                type="date"
                value={form.deadline}
                onChange={(e) => setField("deadline", e.target.value)}
              />
            </Field>
            <Field label="Job type">
              <select
                className="cc-input"
                value={form.employment_type}
                onChange={(e) => setField("employment_type", e.target.value as EmploymentType)}
              >
                {Object.entries(EMPLOYMENT_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Work mode">
              <select
                className="cc-input"
                value={form.work_from}
                onChange={(e) => setField("work_from", e.target.value as WorkFrom)}
              >
                {Object.entries(WORK_FROM_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Description *" error={fieldErrors.description} wide>
              <textarea
                className="cc-input cc-textarea"
                rows={5}
                value={form.description}
                placeholder="What the role involves and who you're looking for."
                aria-invalid={Boolean(fieldErrors.description)}
                onChange={(e) => setField("description", e.target.value)}
              />
            </Field>
          </div>

          {saveError && (
            <p className="cc-error" role="alert">
              {saveError}
            </p>
          )}

          <div className="cc-form-actions">
            <button type="submit" className="cc-upload-btn" disabled={saving}>
              {saving ? "Saving..." : editing === "new" ? "Post job" : "Save changes"}
            </button>
            <button type="button" className="cc-upload-btn cc-btn-secondary" onClick={closeForm} disabled={saving}>
              Cancel
            </button>
          </div>
        </form>
      )}

      {loadError && (
        <p className="cc-error" role="alert">
          {loadError}
        </p>
      )}

      {loading ? (
        <p className="cc-muted">Loading your postings...</p>
      ) : postings.length === 0 ? (
        !loadError && (
          <div className="cc-postings-empty">
            <h2 className="cc-section-title">Post your first job</h2>
            <p>It shows up here, and job seekers can find it in search.</p>
          </div>
        )
      ) : (
        <ul className="cc-postings">
          {postings.map((p) => {
            const closed = p.status === "closed";
            return (
              <li key={p.id} className={`cc-posting ${closed ? "is-closed" : ""}`}>
                <div className="cc-posting-info">
                  <div className="cc-posting-title-row">
                    <h3 className="cc-posting-title">{p.title}</h3>
                    <span className={`cc-status ${closed ? "is-closed" : ""}`}>{closed ? "Closed" : "Open"}</span>
                  </div>
                  <p className="cc-posting-meta">
                    {p.company} · {p.location}
                    {p.deadline && ` · Apply by ${formatDeadline(p.deadline)}`}
                  </p>
                  <ul className="cc-chips">
                    {p.category && <li className="cc-chip">{p.category}</li>}
                    <li className="cc-chip">{EMPLOYMENT_LABELS[p.employment_type]}</li>
                    <li className="cc-chip">{WORK_FROM_LABELS[p.work_from]}</li>
                  </ul>
                </div>
                <div className="cc-posting-actions">
                  <button
                    type="button"
                    className="cc-small-btn"
                    onClick={() => openEditForm(p)}
                    disabled={busyId === p.id}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="cc-small-btn"
                    onClick={() => toggleStatus(p)}
                    disabled={busyId === p.id}
                  >
                    {closed ? "Reopen" : "Close"}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
