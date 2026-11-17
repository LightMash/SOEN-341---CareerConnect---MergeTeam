import { useEffect, useState } from "react";
import QualificationPicker from "./QualificationPicker";
import ResumeImport from "./ResumeImport";
import { getMyQualifications, saveMyQualifications } from "./matchingApi";
import type { Qualification, QualificationSource, SeekerQualification } from "./matchingApi";
import "./matching.css";

// The job seeker's qualifications on the Profile tab. Changes made with the
// search box save right away; resume import shows a checklist first and only
// saves what the seeker confirms.

export default function QualificationsSection({ token }: { token: string }) {
  const [items, setItems] = useState<SeekerQualification[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    getMyQualifications(token)
      .then(setItems)
      .catch((err: Error) => setError(`Couldn't load your qualifications. ${err.message}`))
      .finally(() => setLoading(false));
  }, [token]);

  // Returns whether it saved, so the import panel only closes on success.
  async function save(next: { key: string; source: QualificationSource }[], message: string): Promise<boolean> {
    setSaving(true);
    setError("");
    setNotice("");
    try {
      setItems(await saveMyQualifications(next, token));
      setNotice(message);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save. Try again.");
      return false;
    } finally {
      setSaving(false);
    }
  }

  const current = items.map((q) => ({ key: q.key, source: q.source }));

  function add(q: Qualification) {
    save([...current, { key: q.key, source: "manual" }], `Added ${q.name}`);
  }

  function remove(key: string) {
    const name = items.find((q) => q.key === key)?.name ?? "it";
    save(current.filter((q) => q.key !== key), `Removed ${name}`);
  }

  async function confirmImport(chosen: { key: string; source: QualificationSource }[]) {
    const have = new Set(current.map((q) => q.key));
    const added = chosen.filter((c) => !have.has(c.key));
    if (await save([...current, ...added], `Added ${added.length} from your resume`)) setImporting(false);
  }

  return (
    <section className="cc-section" aria-labelledby="cc-quals-title">
      <div className="cc-quals-head">
        <h2 className="cc-section-title" id="cc-quals-title">
          Qualifications
        </h2>
        {!importing && (
          <button type="button" className="cc-upload-btn cc-btn-secondary" onClick={() => setImporting(true)}>
            Import from resume
          </button>
        )}
      </div>
      <p className="cc-muted">
        Degrees, licences, certifications, languages and skills from the standard list. Job listings are matched
        against these.
      </p>

      {notice && (
        <p className="cc-success" role="status">
          {notice}
        </p>
      )}
      {error && (
        <p className="cc-error" role="alert">
          {error}
        </p>
      )}

      {importing && (
        <ResumeImport token={token} onCancel={() => setImporting(false)} onConfirm={confirmImport} />
      )}

      {loading ? (
        <p className="cc-muted">Loading qualifications…</p>
      ) : (
        <QualificationPicker
          token={token}
          label="Your qualifications"
          selected={items}
          onAdd={add}
          onRemove={remove}
          disabled={saving}
        />
      )}
    </section>
  );
}
