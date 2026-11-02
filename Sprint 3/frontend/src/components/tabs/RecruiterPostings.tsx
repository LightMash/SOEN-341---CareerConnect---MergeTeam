import { useEffect, useState } from "react";
import type { SubmitEvent, ReactNode } from "react";
import {
  listMyPostings,
  createPosting,
  updatePosting,
  closePosting,
  reopenPosting,
  JOB_TYPES,
  MAX_DESCRIPTION,
  MAX_SALARY,
} from "../../postingsApi";
import type { JobPosting, JobPostingInput, JobType } from "../../postingsApi";
import "../../styles/postings.css";
import RecruiterApplicants from "./RecruiterApplicants";
import "../../styles/applicants.css";

// Recruiter side of the Job dashboard (US-04, Task 4.3): a list of the
// recruiter's own postings plus one form used for both creating and editing.

// Salaries are typed into text boxes, so the form keeps them as strings
// ("" = not disclosed) and converts them to numbers only when saving.
type FormState = Omit<JobPostingInput, "salary_min" | "salary_max"> & {
  salary_min: string;
  salary_max: string;
};
type CheckedField = "title" | "company" | "location" | "description" | "salary_min" | "salary_max";

const EMPTY_FORM: FormState = {
  title: "",
  company: "",
  location: "",
  category: "",
  job_type: "Full-time",
  description: "",
  salary_min: "",
  salary_max: "",
};

const REQUIRED: [CheckedField, string][] = [
  ["title", "Enter a job title"],
  ["company", "Enter the company name"],
  ["location", "Enter a location"],
  ["description", "Add a short description"],
];

function validate(form: FormState) {
  const errors: Partial<Record<CheckedField, string>> = {};

  for (const [key, message] of REQUIRED) {
    if (!form[key].trim()) errors[key] = message;
  }
  if (form.description.length > MAX_DESCRIPTION) {
    errors.description = `Keep the description under ${MAX_DESCRIPTION.toLocaleString()} characters`;
  }

  for (const key of ["salary_min", "salary_max"] as const) {
    const value = form[key].trim();
    if (value && (!/^\d+$/.test(value) || Number(value) > MAX_SALARY)) {
      errors[key] = `Enter a whole number from 0 to ${MAX_SALARY.toLocaleString()}`;
    }
  }
  if (!errors.salary_min && !errors.salary_max && form.salary_min.trim() && form.salary_max.trim()) {
    if (Number(form.salary_min) > Number(form.salary_max)) {
      errors.salary_max = "Maximum can't be lower than the minimum";
    }
  }

  return errors;
}

function toSalary(value: string): number | null {
  return value.trim() ? Number(value) : null;
}

function formatSalary(min: number | null, max: number | null) {
  const money = (n: number) => `$${n.toLocaleString()}`;
  if (min !== null && max !== null) return `${money(min)} – ${money(max)} CAD / year`;
  if (min !== null) return `From ${money(min)} CAD / year`;
  if (max !== null) return `Up to ${money(max)} CAD / year`;
  return "Salary not disclosed";
}

// Open postings first, newest first inside each group.
function sortPostings(list: JobPosting[]) {
  return [...list].sort((a, b) => {
    if (a.is_open !== b.is_open) return a.is_open ? -1 : 1;
    return b.created_at.localeCompare(a.created_at);
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
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<CheckedField, string>>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const [notice, setNotice] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [expandedApplicantsId, setExpandedApplicantsId] =
    useState<number | null>(null);

  function toggleApplicants(jobId: number) {
    setExpandedApplicantsId(current =>
      current === jobId ? null : jobId
    );
  }

  useEffect(() => {
    listMyPostings(token)
      .then((list) => setPostings(sortPostings(list)))
      .catch((err: Error) => setLoadError(`Couldn't load your postings. ${err.message}`))
      .finally(() => setLoading(false));
  }, [token]);

  const openCount = postings.filter((p) => p.is_open).length;

  function openNewForm() {
    setExpandedApplicantsId(null); // NEW
    setEditing("new");
    setForm(EMPTY_FORM);
    setFieldErrors({});
    setSaveError("");
    setNotice("");
  }

  function openEditForm(posting: JobPosting) {
    setExpandedApplicantsId(null); // NEW
    setEditing(posting.id);
    setForm({
      title: posting.title,
      company: posting.company,
      location: posting.location,
      category: posting.category,
      job_type: posting.job_type,
      description: posting.description,
      salary_min: posting.salary_min === null ? "" : String(posting.salary_min),
      salary_max: posting.salary_max === null ? "" : String(posting.salary_max),
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

    const errors = validate(form);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    // PUT replaces every editable field, so always send the whole form.
    const input: JobPostingInput = {
      title: form.title.trim(),
      company: form.company.trim(),
      location: form.location.trim(),
      category: form.category.trim(),
      job_type: form.job_type,
      description: form.description.trim(),
      salary_min: toSalary(form.salary_min),
      salary_max: toSalary(form.salary_max),
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

  async function toggleOpen(posting: JobPosting) {
    setBusyId(posting.id);
    setNotice("");
    setLoadError("");
    try {
      const updated = posting.is_open
        ? await closePosting(posting.id, token)
        : await reopenPosting(posting.id, token);
      setPostings((prev) => sortPostings(prev.map((p) => (p.id === updated.id ? updated : p))));
      setNotice(updated.is_open ? "Posting reopened" : "Posting closed");
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Couldn't update the posting. Try again.");
      // The posting may have changed elsewhere (e.g. already closed), so reload the real state.
      listMyPostings(token)
        .then((list) => setPostings(sortPostings(list)))
        .catch(() => {});
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
            <Field label="Job type">
              <select
                className="cc-input"
                value={form.job_type}
                onChange={(e) => setField("job_type", e.target.value as JobType)}
              >
                {JOB_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Minimum salary (CAD / year)" error={fieldErrors.salary_min}>
              <input
                className="cc-input"
                inputMode="numeric"
                value={form.salary_min}
                placeholder="Optional"
                aria-invalid={Boolean(fieldErrors.salary_min)}
                onChange={(e) => setField("salary_min", e.target.value)}
              />
            </Field>
            <Field label="Maximum salary (CAD / year)" error={fieldErrors.salary_max}>
              <input
                className="cc-input"
                inputMode="numeric"
                value={form.salary_max}
                placeholder="Optional"
                aria-invalid={Boolean(fieldErrors.salary_max)}
                onChange={(e) => setField("salary_max", e.target.value)}
              />
            </Field>
            <Field label="Description *" error={fieldErrors.description} wide>
              <textarea
                className="cc-input cc-textarea"
                rows={5}
                value={form.description}
                maxLength={MAX_DESCRIPTION}
                placeholder="What the role involves and who you're looking for."
                aria-invalid={Boolean(fieldErrors.description)}
                onChange={(e) => setField("description", e.target.value)}
              />
              <span className="cc-field-hint">
                {form.description.length.toLocaleString()} / {MAX_DESCRIPTION.toLocaleString()}
              </span>
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
            const closed = !p.is_open;
            return (
              <li key={p.id} className={`cc-posting ${closed ? "is-closed" : ""}`}>
                <div className="cc-posting-info">
                  <div className="cc-posting-title-row">
                    <h3 className="cc-posting-title">{p.title}</h3>
                    <span className={`cc-status ${closed ? "is-closed" : ""}`}>{closed ? "Closed" : "Open"}</span>
                  </div>
                  <p className="cc-posting-meta">
                    {p.company}
                    {p.location && ` · ${p.location}`}
                    {` · ${formatSalary(p.salary_min, p.salary_max)}`}
                  </p>
                  <ul className="cc-chips">
                    {p.category && <li className="cc-chip">{p.category}</li>}
                    <li className="cc-chip">{p.job_type}</li>
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
                    onClick={() => toggleOpen(p)}
                    disabled={busyId === p.id}
                  >
                    {closed ? "Reopen" : "Close"}
                  </button>
                  <button
                    type="button"
                    className="cc-small-btn"
                    aria-expanded={expandedApplicantsId === p.id}
                    aria-controls={`applicants-panel-${p.id}`}
                    onClick={() => toggleApplicants(p.id)}
                    disabled={editing !== null}
                  >
                    {expandedApplicantsId === p.id
                      ? "Hide applicants"
                      : "Applicants"}
                  </button>
                </div>
                {expandedApplicantsId === p.id && (
                  <div
                    id={`applicants-panel-${p.id}`}
                    className="cc-applicants-panel"
                  >
                    <RecruiterApplicants
                      jobId={p.id}
                      token={token}
                    />
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
