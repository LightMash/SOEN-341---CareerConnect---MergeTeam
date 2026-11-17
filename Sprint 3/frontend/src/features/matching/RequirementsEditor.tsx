import { useEffect, useImperativeHandle, useState } from "react";
import type { Ref } from "react";
import QualificationPicker from "./QualificationPicker";
import { getRequirements, saveRequirements } from "./matchingApi";
import type { Qualification } from "./matchingApi";

// Requirements editor inside the recruiter's posting form. The posting itself
// is saved first by RecruiterPostings (unchanged request body); then it calls
// save(jobId) on this editor, which PUTs the requirements separately.

export interface RequirementsEditorHandle {
  save: (jobId: number) => Promise<void>;
}

interface Draft {
  qualification: Qualification;
  is_required: boolean;
  weight: number;
}

interface RequirementsEditorProps {
  token: string;
  // The posting being edited, or null for a new one (nothing to load yet).
  jobId: number | null;
  ref?: Ref<RequirementsEditorHandle>;
}

export default function RequirementsEditor({ token, jobId, ref }: RequirementsEditorProps) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [loading, setLoading] = useState(jobId !== null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (jobId === null) return;
    let cancelled = false;
    getRequirements(jobId, token)
      .then((reqs) => {
        if (cancelled) return;
        setDrafts(reqs.map((r) => ({ qualification: r, is_required: r.is_required, weight: r.weight })));
      })
      .catch((err: Error) => {
        if (!cancelled) setError(`Couldn't load the requirements. ${err.message}`);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, token]);

  useImperativeHandle(
    ref,
    () => ({
      async save(id: number) {
        await saveRequirements(
          id,
          drafts.map((d) => ({
            key: d.qualification.key,
            is_required: d.is_required,
            weight: d.is_required ? 1 : d.weight,
          })),
          token
        );
      },
    }),
    [drafts, token]
  );

  function update(key: string, change: Partial<Draft>) {
    setDrafts((prev) => prev.map((d) => (d.qualification.key === key ? { ...d, ...change } : d)));
  }

  const byKey = new Map(drafts.map((d) => [d.qualification.key, d]));

  return (
    <fieldset className="cc-req-editor" disabled={loading}>
      <legend className="cc-subhead">Qualifications</legend>
      <p className="cc-muted">
        Pick from the standard list. <strong>Required</strong> items decide who qualifies;{" "}
        <strong>Bonus</strong> items (weight 1–3) only affect how qualified applicants compare.
      </p>
      {loading && <p className="cc-muted">Loading requirements…</p>}
      {error && (
        <p className="cc-error" role="alert">
          {error}
        </p>
      )}
      <QualificationPicker
        token={token}
        label="Listing qualifications"
        selected={drafts.map((d) => d.qualification)}
        onAdd={(q) => setDrafts((prev) => [...prev, { qualification: q, is_required: true, weight: 1 }])}
        onRemove={(key) => setDrafts((prev) => prev.filter((d) => d.qualification.key !== key))}
        renderChipExtra={(q) => {
          const draft = byKey.get(q.key);
          if (!draft) return null;
          return (
            <span className="cc-req-controls">
              <button
                type="button"
                className={`cc-req-toggle ${draft.is_required ? "is-required" : "is-bonus"}`}
                aria-pressed={draft.is_required}
                aria-label={`${q.name}: ${draft.is_required ? "required" : "bonus"}. Switch to ${
                  draft.is_required ? "bonus" : "required"
                }`}
                onClick={() => update(q.key, { is_required: !draft.is_required })}
              >
                {draft.is_required ? "Required" : "Bonus"}
              </button>
              {!draft.is_required && (
                <select
                  className="cc-req-weight"
                  aria-label={`Weight for ${q.name}`}
                  value={draft.weight}
                  onChange={(e) => update(q.key, { weight: Number(e.target.value) })}
                >
                  <option value={1}>Weight 1</option>
                  <option value={2}>Weight 2</option>
                  <option value={3}>Weight 3</option>
                </select>
              )}
            </span>
          );
        }}
      />
    </fieldset>
  );
}
