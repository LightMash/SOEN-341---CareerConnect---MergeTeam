import { useEffect, useId, useState } from "react";
import type { ReactNode } from "react";
import {
  CATEGORIES,
  CATEGORY_LABELS,
  createCustomQualification,
  searchQualifications,
} from "./matchingApi";
import type { Category, Qualification, SearchResult } from "./matchingApi";

// Search box for the standard qualification list, shared by job seekers
// (their profile) and recruiters (listing requirements). Typed wording is
// matched onto list entries by the backend, so "doctorate in comp sci" and
// "PhD Computer Science" end up as the same qualification.

const DEBOUNCE_MS = 300;

interface QualificationPickerProps {
  token: string;
  label: string;
  selected: Qualification[];
  onAdd: (qualification: Qualification) => void;
  onRemove: (key: string) => void;
  // Extra controls inside each chip (the recruiter's Required/Bonus toggle).
  renderChipExtra?: (qualification: Qualification) => ReactNode;
  disabled?: boolean;
}

export default function QualificationPicker({
  token,
  label,
  selected,
  onAdd,
  onRemove,
  renderChipExtra,
  disabled = false,
}: QualificationPickerProps) {
  const inputId = useId();
  const [text, setText] = useState("");
  const [category, setCategory] = useState<Category | "">("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  // "Add as new" is a two-step action: first show "Did you mean…?".
  const [confirmingNew, setConfirmingNew] = useState(false);
  const [newCategory, setNewCategory] = useState<Category>("skill");
  const [creating, setCreating] = useState(false);

  const query = text.trim();

  useEffect(() => {
    if (!query) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      setSearching(true);
      searchQualifications(query, category, token)
        .then((data) => {
          if (!cancelled) {
            setResults(data);
            setError("");
          }
        })
        .catch((err: Error) => {
          if (!cancelled) setError(err.message);
        })
        .finally(() => {
          if (!cancelled) setSearching(false);
        });
    }, DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, category, token]);

  const selectedKeys = new Set(selected.map((q) => q.key));
  const visibleResults = query ? results.filter((r) => !selectedKeys.has(r.key)) : [];

  function reset() {
    setText("");
    setResults([]);
    setConfirmingNew(false);
  }

  function choose(qualification: Qualification) {
    onAdd(qualification);
    reset();
  }

  function startAddNew() {
    setNewCategory(category || "skill");
    setConfirmingNew(true);
  }

  async function createNew() {
    setCreating(true);
    setError("");
    try {
      const created = await createCustomQualification(newCategory, query, token);
      if (!selectedKeys.has(created.key)) onAdd(created);
      reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add it. Try again.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="cc-qpicker">
      {selected.length > 0 ? (
        <ul className="cc-qchips" aria-label={`Selected: ${label}`}>
          {selected.map((q) => (
            <li key={q.key} className="cc-qchip">
              <span className="cc-qchip-name">
                {q.name}
                {q.custom && <span className="cc-qchip-tag"> (unverified)</span>}
              </span>
              {renderChipExtra?.(q)}
              <button
                type="button"
                className="cc-qchip-remove"
                aria-label={`Remove ${q.name}`}
                onClick={() => onRemove(q.key)}
                disabled={disabled}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="cc-muted">None added yet.</p>
      )}

      <div className="cc-qpicker-row">
        <label className="cc-visually-hidden" htmlFor={inputId}>
          {label}
        </label>
        <input
          id={inputId}
          className="cc-input"
          type="search"
          placeholder="Search: degree, licence, language, skill…"
          value={text}
          disabled={disabled}
          autoComplete="off"
          onChange={(e) => {
            setText(e.target.value);
            setConfirmingNew(false);
            if (!e.target.value.trim()) setResults([]);
          }}
        />
        <select
          className="cc-input cc-qpicker-category"
          aria-label="Filter by category"
          value={category}
          disabled={disabled}
          onChange={(e) => setCategory(e.target.value as Category | "")}
        >
          <option value="">All categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {CATEGORY_LABELS[c]}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <p className="cc-error" role="alert">
          {error}
        </p>
      )}

      {query && !confirmingNew && (
        <div className="cc-qresults" aria-live="polite">
          {searching && visibleResults.length === 0 && <p className="cc-muted">Searching…</p>}
          {visibleResults.length > 0 && (
            <ul className="cc-qresult-list">
              {visibleResults.map((r) => (
                <li key={r.key}>
                  <button type="button" className="cc-qresult" onClick={() => choose(r)} disabled={disabled}>
                    <span>{r.name}</span>
                    <span className="cc-muted">
                      {CATEGORY_LABELS[r.category]}
                      {r.custom ? " · unverified" : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {!searching && visibleResults.length === 0 && <p className="cc-muted">Nothing in the list matches.</p>}
          <button type="button" className="cc-qadd-new" onClick={startAddNew} disabled={disabled}>
            Add “{query}” as new
          </button>
        </div>
      )}

      {query && confirmingNew && (
        <div className="cc-qconfirm" role="group" aria-label="Add a new qualification">
          {visibleResults.length > 0 && (
            <>
              <p className="cc-qconfirm-title">Did you mean…?</p>
              <ul className="cc-qresult-list">
                {visibleResults.slice(0, 3).map((r) => (
                  <li key={r.key}>
                    <button type="button" className="cc-qresult" onClick={() => choose(r)}>
                      <span>{r.name}</span>
                      <span className="cc-muted">{CATEGORY_LABELS[r.category]}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
          <div className="cc-qpicker-row">
            <select
              className="cc-input cc-qpicker-category"
              aria-label="Category of the new qualification"
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value as Category)}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {CATEGORY_LABELS[c]}
                </option>
              ))}
            </select>
            <button type="button" className="cc-upload-btn" onClick={createNew} disabled={creating}>
              {creating ? "Adding…" : `No, add “${query}” as new`}
            </button>
            <button type="button" className="cc-upload-btn cc-btn-secondary" onClick={() => setConfirmingNew(false)}>
              Back
            </button>
          </div>
          <p className="cc-muted">New entries aren't in the standard list, so they're marked unverified.</p>
        </div>
      )}
    </div>
  );
}
