import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import type { Profile, ProfileUpdate } from "../../api";
import { getMyProfile, updateMyProfile } from "../../api";
import ProfilePhoto from "../ProfilePhoto";
import ResumeManager from "../ResumeManager";

// The Profile tab: a read-only view of the user's professional profile with
// an "Edit profile" form, followed by the resume manager (upload / replace /
// primary / delete). Job seekers only — Dashboard.tsx hides this tab for
// recruiters, and the backend also returns 403 for them.

interface ProfileTabProps {
  token: string;
  fullName: string; // for the initials shown when there is no photo
  // The current photo (blob URL) and a way to change it. The photo is owned
  // by Dashboard.tsx so the sidebar avatar updates the moment this tab does.
  photoUrl: string | null;
  onPhotoChange: (url: string | null) => void;
}

// ---- Form state ----------------------------------------------------------
// <input> values are always strings, so the edit form keeps years as strings
// and skills as ONE comma-separated string. toDraft() converts a saved
// Profile into this shape and toPayload() converts back to what the backend
// expects, so the conversion rules live in exactly two places.

interface EducationDraft {
  school: string;
  degree: string;
  start_year: string;
  end_year: string;
}

interface ExperienceDraft {
  company: string;
  title: string;
  description: string;
  start_year: string;
  end_year: string;
}

interface ProfileDraft {
  headline: string;
  location: string;
  phone: string;
  summary: string;
  skills: string; // "Python, React, SQL"
  education: EducationDraft[];
  experience: ExperienceDraft[];
  linkedin_url: string;
  github_url: string;
  portfolio_url: string;
}

const EMPTY_DRAFT: ProfileDraft = {
  headline: "",
  location: "",
  phone: "",
  summary: "",
  skills: "",
  education: [],
  experience: [],
  linkedin_url: "",
  github_url: "",
  portfolio_url: "",
};

// null <-> "" for year inputs: an empty box means "no year" (e.g. still studying).
const yearToString = (y: number | null) => (y === null ? "" : String(y));
const stringToYear = (s: string) => (s.trim() === "" ? null : Number(s));

function toDraft(p: Profile): ProfileDraft {
  return {
    headline: p.headline,
    location: p.location,
    phone: p.phone,
    summary: p.summary,
    skills: p.skills.join(", "),
    education: p.education.map((e) => ({
      school: e.school,
      degree: e.degree,
      start_year: yearToString(e.start_year),
      end_year: yearToString(e.end_year),
    })),
    experience: p.experience.map((x) => ({
      company: x.company,
      title: x.title,
      description: x.description,
      start_year: yearToString(x.start_year),
      end_year: yearToString(x.end_year),
    })),
    linkedin_url: p.linkedin_url,
    github_url: p.github_url,
    portfolio_url: p.portfolio_url,
  };
}

function toPayload(d: ProfileDraft): ProfileUpdate {
  return {
    headline: d.headline,
    location: d.location,
    phone: d.phone,
    summary: d.summary,
    // "a, b,, c " -> ["a", "b", "c"]. The backend also trims and de-duplicates.
    skills: d.skills.split(",").map((s) => s.trim()).filter(Boolean),
    education: d.education.map((e) => ({
      school: e.school,
      degree: e.degree,
      start_year: stringToYear(e.start_year),
      end_year: stringToYear(e.end_year),
    })),
    experience: d.experience.map((x) => ({
      company: x.company,
      title: x.title,
      description: x.description,
      start_year: stringToYear(x.start_year),
      end_year: stringToYear(x.end_year),
    })),
    linkedin_url: d.linkedin_url,
    github_url: d.github_url,
    portfolio_url: d.portfolio_url,
  };
}

// "2021 – 2025", "2023 – Present", or "" when neither year is set.
function yearRange(start: number | null, end: number | null) {
  if (start === null && end === null) return "";
  return `${start ?? ""} – ${end ?? "Present"}`;
}

// ---- Small presentational helpers ----------------------------------------

// A labelled form control. Wrapping the input in <label> links the two for
// screen readers and makes clicking the label focus the input.
function Field({ label, wide, children }: { label: string; wide?: boolean; children: ReactNode }) {
  return (
    <label className={`cc-field ${wide ? "is-wide" : ""}`}>
      <span className="cc-field-label">{label}</span>
      {children}
    </label>
  );
}

// One label/value row of the read-only view. An empty value renders a muted
// "Not added yet" so new users see what they can fill in.
function ViewRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="cc-kv-row">
      <dt>{label}</dt>
      <dd>{children || <span className="cc-muted">Not added yet</span>}</dd>
    </div>
  );
}

function LinkValue({ url }: { url: string }) {
  if (!url) return null;
  // Safe to use as an href: the backend only ever stores http(s) links (see
  // _check_url in schemas/profile.py), so a "javascript:" URL can't get here.
  // rel="noopener noreferrer" stops the opened page from controlling this tab.
  return (
    <a className="cc-link" href={url} target="_blank" rel="noopener noreferrer">
      {url}
    </a>
  );
}

// ---- The tab ---------------------------------------------------------------

export default function ProfileTab({ token, fullName, photoUrl, onPhotoChange }: ProfileTabProps) {
  // `profile` is what is SAVED on the server (what the read-only view shows).
  // `draft` is the in-progress edit form. Keeping them separate is what makes
  // Cancel and failed saves safe: the saved data is never touched until the
  // backend confirms a successful save.
  const [profile, setProfile] = useState<Profile | null>(null);
  const [draft, setDraft] = useState<ProfileDraft>(EMPTY_DRAFT);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // Fetch-on-mount: load the saved profile (the backend creates an empty one
  // the first time a user asks for it).
  useEffect(() => {
    getMyProfile(token)
      .then((p) => {
        setProfile(p);
        setDraft(toDraft(p));
      })
      .catch(() => setError("Couldn't load your profile. Try refreshing the page."));
  }, [token]);

  // Called by ResumeManager after an upload/delete. Only the completeness
  // number and the "missing" list are updated — never the rest of `profile` —
  // so a refresh can't overwrite anything the user is typing into the edit form.
  function refreshCompleteness() {
    getMyProfile(token)
      .then((fresh) =>
        setProfile((prev) =>
          prev ? { ...prev, completeness: fresh.completeness, missing: fresh.missing } : fresh
        )
      )
      .catch(() => {
        /* the bar just keeps its old value */
      });
  }

  function startEdit() {
    if (!profile) return;
    setDraft(toDraft(profile)); // always start from the saved data
    setError("");
    setMessage("");
    setEditing(true);
  }

  function cancelEdit() {
    setEditing(false); // the draft is simply thrown away
    setError("");
  }

  // Updates one top-level field of the draft. The generic <K> ties the value's
  // type to the key, so setField("skills", 5) is a compile error.
  function setField<K extends keyof ProfileDraft>(key: K, value: ProfileDraft[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  // Education / experience rows are edited immutably: each handler builds a
  // new array (map/filter/spread) instead of mutating, so React sees the change.
  function updateEducation(i: number, key: keyof EducationDraft, value: string) {
    setDraft((d) => ({
      ...d,
      education: d.education.map((row, idx) => (idx === i ? { ...row, [key]: value } : row)),
    }));
  }
  function addEducation() {
    setDraft((d) => ({
      ...d,
      education: [...d.education, { school: "", degree: "", start_year: "", end_year: "" }],
    }));
  }
  function removeEducation(i: number) {
    setDraft((d) => ({ ...d, education: d.education.filter((_, idx) => idx !== i) }));
  }

  function updateExperience(i: number, key: keyof ExperienceDraft, value: string) {
    setDraft((d) => ({
      ...d,
      experience: d.experience.map((row, idx) => (idx === i ? { ...row, [key]: value } : row)),
    }));
  }
  function addExperience() {
    setDraft((d) => ({
      ...d,
      experience: [
        ...d.experience,
        { company: "", title: "", description: "", start_year: "", end_year: "" },
      ],
    }));
  }
  function removeExperience(i: number) {
    setDraft((d) => ({ ...d, experience: d.experience.filter((_, idx) => idx !== i) }));
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault(); // stop the browser from reloading the page on submit

    // Quick client checks give a friendlier message than the generic 422
    // text; the backend validates everything again regardless.
    if (draft.education.some((row) => !row.school.trim())) {
      setError("Each education entry needs a school name.");
      return;
    }
    if (draft.experience.some((row) => !row.company.trim() || !row.title.trim())) {
      setError("Each experience entry needs a company and a job title.");
      return;
    }

    setError("");
    setSaving(true);
    try {
      // The backend returns the saved profile (with a fresh completeness);
      // showing THAT, not our draft, means the screen matches what's stored
      // (e.g. skills come back trimmed and de-duplicated).
      const saved = await updateMyProfile(toPayload(draft), token);
      setProfile(saved);
      setDraft(toDraft(saved));
      setEditing(false);
      setMessage("Profile saved.");
    } catch (err) {
      // `profile` was not touched, so the previously saved data stays on
      // screen and the form stays open with the user's edits intact.
      setError(err instanceof Error ? err.message : "Couldn't save your profile.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <header className="cc-main-head">
        <div>
          <h1 className="cc-title">Profile</h1>
          <p className="cc-subtitle">Your professional information and resumes</p>
        </div>

        {!editing && profile && (
          <button type="button" className="cc-upload-btn" onClick={startEdit}>
            Edit profile
          </button>
        )}
      </header>

      {/* Photo block: shared with the recruiter's profile tab. */}
      <ProfilePhoto token={token} fullName={fullName} photoUrl={photoUrl} onPhotoChange={onPhotoChange} />

      {/* Completeness bar. The percentage is computed by the backend (one
          shared definition of "complete"); this only draws it. It is hidden
          entirely once the profile hits 100%: there is nothing left to nudge
          the user about, and it reappears automatically if a required
          section is emptied again (e.g. the last resume is deleted). */}
      {profile && profile.completeness < 100 && (
        <section className="cc-meter" aria-label="Profile completeness">
          <div className="cc-meter-row">
            <span>Profile completeness</span>
            <strong>{profile.completeness}%</strong>
          </div>
          <div
            className="cc-meter-bar"
            role="progressbar"
            aria-valuenow={profile.completeness}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div className="cc-meter-fill" style={{ width: `${profile.completeness}%` }} />
          </div>
          {/* The backend decides what counts and what's missing (see
              _completeness in routers/profile.py); this only displays it. */}
          <p className="cc-muted">
            Still missing: <strong>{profile.missing.join(", ")}</strong>
          </p>
        </section>
      )}

      {message && (
        <p className="cc-success" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="cc-error" role="alert">
          {error}
        </p>
      )}

      {/* One slot that is EITHER the edit form OR the read-only view. Keeping
          it a single slot means <ResumeManager> below stays at the same place
          in the React tree and is not remounted (and re-fetched) every time
          the user starts or stops editing. */}
      {editing ? (
        <form className="cc-section" onSubmit={handleSave}>
          <h2 className="cc-section-title">Edit profile</h2>

          <div className="cc-form-grid">
            <Field label="Headline">
              <input
                className="cc-input"
                value={draft.headline}
                maxLength={120}
                placeholder="e.g. Software Engineering Student"
                onChange={(e) => setField("headline", e.target.value)}
              />
            </Field>
            <Field label="Location">
              <input
                className="cc-input"
                value={draft.location}
                maxLength={120}
                placeholder="e.g. Montréal, QC"
                onChange={(e) => setField("location", e.target.value)}
              />
            </Field>
            <Field label="Phone (optional)">
              <input
                className="cc-input"
                value={draft.phone}
                maxLength={30}
                onChange={(e) => setField("phone", e.target.value)}
              />
            </Field>
            <Field label="Skills (comma separated)">
              <input
                className="cc-input"
                value={draft.skills}
                placeholder="Python, React, SQL"
                onChange={(e) => setField("skills", e.target.value)}
              />
            </Field>
            <Field label="Summary" wide>
              <textarea
                className="cc-input cc-textarea"
                value={draft.summary}
                maxLength={2000}
                rows={4}
                onChange={(e) => setField("summary", e.target.value)}
              />
            </Field>
          </div>

          <h3 className="cc-subhead">Education</h3>
          {draft.education.map((row, i) => (
            // Index as key is fine here: rows have no stable id and are only
            // ever added or removed by this component.
            <div key={i} className="cc-repeat-row">
              <div className="cc-form-grid">
                <Field label="School">
                  <input
                    className="cc-input"
                    value={row.school}
                    maxLength={120}
                    onChange={(e) => updateEducation(i, "school", e.target.value)}
                  />
                </Field>
                <Field label="Degree / program">
                  <input
                    className="cc-input"
                    value={row.degree}
                    maxLength={120}
                    onChange={(e) => updateEducation(i, "degree", e.target.value)}
                  />
                </Field>
                <Field label="Start year">
                  <input
                    className="cc-input"
                    type="number"
                    min={1950}
                    max={2100}
                    value={row.start_year}
                    onChange={(e) => updateEducation(i, "start_year", e.target.value)}
                  />
                </Field>
                <Field label="End year (blank = present)">
                  <input
                    className="cc-input"
                    type="number"
                    min={1950}
                    max={2100}
                    value={row.end_year}
                    onChange={(e) => updateEducation(i, "end_year", e.target.value)}
                  />
                </Field>
              </div>
              <button type="button" className="cc-link cc-link-danger" onClick={() => removeEducation(i)}>
                Remove
              </button>
            </div>
          ))}
          <button type="button" className="cc-upload-btn cc-btn-secondary" onClick={addEducation}>
            + Add education
          </button>

          <h3 className="cc-subhead">Experience</h3>
          {draft.experience.map((row, i) => (
            <div key={i} className="cc-repeat-row">
              <div className="cc-form-grid">
                <Field label="Company">
                  <input
                    className="cc-input"
                    value={row.company}
                    maxLength={120}
                    onChange={(e) => updateExperience(i, "company", e.target.value)}
                  />
                </Field>
                <Field label="Job title">
                  <input
                    className="cc-input"
                    value={row.title}
                    maxLength={120}
                    onChange={(e) => updateExperience(i, "title", e.target.value)}
                  />
                </Field>
                <Field label="Start year">
                  <input
                    className="cc-input"
                    type="number"
                    min={1950}
                    max={2100}
                    value={row.start_year}
                    onChange={(e) => updateExperience(i, "start_year", e.target.value)}
                  />
                </Field>
                <Field label="End year (blank = present)">
                  <input
                    className="cc-input"
                    type="number"
                    min={1950}
                    max={2100}
                    value={row.end_year}
                    onChange={(e) => updateExperience(i, "end_year", e.target.value)}
                  />
                </Field>
                <Field label="Description" wide>
                  <textarea
                    className="cc-input cc-textarea"
                    value={row.description}
                    maxLength={1000}
                    rows={3}
                    onChange={(e) => updateExperience(i, "description", e.target.value)}
                  />
                </Field>
              </div>
              <button type="button" className="cc-link cc-link-danger" onClick={() => removeExperience(i)}>
                Remove
              </button>
            </div>
          ))}
          <button type="button" className="cc-upload-btn cc-btn-secondary" onClick={addExperience}>
            + Add experience
          </button>

          <h3 className="cc-subhead">Links</h3>
          <div className="cc-form-grid">
            <Field label="LinkedIn">
              <input
                className="cc-input"
                value={draft.linkedin_url}
                placeholder="https://linkedin.com/in/..."
                onChange={(e) => setField("linkedin_url", e.target.value)}
              />
            </Field>
            <Field label="GitHub">
              <input
                className="cc-input"
                value={draft.github_url}
                placeholder="https://github.com/..."
                onChange={(e) => setField("github_url", e.target.value)}
              />
            </Field>
            <Field label="Portfolio / website" wide>
              <input
                className="cc-input"
                value={draft.portfolio_url}
                placeholder="https://..."
                onChange={(e) => setField("portfolio_url", e.target.value)}
              />
            </Field>
          </div>

          <div className="cc-form-actions">
            <button type="submit" className="cc-upload-btn" disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              type="button"
              className="cc-upload-btn cc-btn-secondary"
              onClick={cancelEdit}
              disabled={saving}
            >
              Cancel
            </button>
          </div>
        </form>
      ) : profile ? (
        <section className="cc-section">
          <h2 className="cc-section-title">About</h2>
          <dl className="cc-kv">
            <ViewRow label="Headline">{profile.headline}</ViewRow>
            <ViewRow label="Location">{profile.location}</ViewRow>
            <ViewRow label="Phone">{profile.phone}</ViewRow>
            <ViewRow label="Summary">
              {/* cc-prewrap keeps the line breaks the user typed. */}
              {profile.summary && <span className="cc-prewrap">{profile.summary}</span>}
            </ViewRow>
            <ViewRow label="Skills">
              {profile.skills.length > 0 && (
                <ul className="cc-chips">
                  {profile.skills.map((skill) => (
                    <li key={skill} className="cc-chip">
                      {skill}
                    </li>
                  ))}
                </ul>
              )}
            </ViewRow>
            <ViewRow label="Education">
              {profile.education.length > 0 && (
                <ul className="cc-entries">
                  {profile.education.map((e, i) => (
                    <li key={i}>
                      <strong>{e.school}</strong>
                      {e.degree && <span> — {e.degree}</span>}
                      <span className="cc-muted"> {yearRange(e.start_year, e.end_year)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </ViewRow>
            <ViewRow label="Experience">
              {profile.experience.length > 0 && (
                <ul className="cc-entries">
                  {profile.experience.map((x, i) => (
                    <li key={i}>
                      <strong>{x.title}</strong> at {x.company}
                      <span className="cc-muted"> {yearRange(x.start_year, x.end_year)}</span>
                      {x.description && <p className="cc-prewrap">{x.description}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </ViewRow>
            <ViewRow label="LinkedIn">
              <LinkValue url={profile.linkedin_url} />
            </ViewRow>
            <ViewRow label="GitHub">
              <LinkValue url={profile.github_url} />
            </ViewRow>
            <ViewRow label="Portfolio">
              <LinkValue url={profile.portfolio_url} />
            </ViewRow>
          </dl>
        </section>
      ) : (
        // Only show "Loading" if nothing went wrong; on a load failure the
        // error message above explains what happened instead.
        !error && <p className="cc-muted">Loading profile...</p>
      )}

      {/* Resume upload / replace / primary / delete. Its onChange refreshes
          the completeness bar above whenever the resume count changes. */}
      <ResumeManager token={token} onChange={refreshCompleteness} />
    </>
  );
}
