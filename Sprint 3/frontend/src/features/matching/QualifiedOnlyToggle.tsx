import { useEffect, useId, useState } from "react";
import { matchListings } from "./matchingApi";
import "./matching.css";

// "Only show jobs I qualify for" for the job feed. It filters the listings
// that are already loaded (the current search results) by asking
// POST /match about them; it does not change the search request itself.
// Reports the ids to keep through onChange, or null for "show everything".

interface QualifiedOnlyToggleProps {
  jobIds: number[];
  token: string;
  onChange: (qualifiedIds: Set<number> | null) => void;
}

export default function QualifiedOnlyToggle({ jobIds, token, onChange }: QualifiedOnlyToggleProps) {
  const id = useId();
  const [enabled, setEnabled] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  // A string key so a new array with the same ids doesn't refetch.
  const idsKey = jobIds.join(",");

  useEffect(() => {
    if (!enabled) {
      onChange(null);
      return;
    }
    let cancelled = false;
    const ids = idsKey ? idsKey.split(",").map(Number) : [];
    setChecking(true);
    setError("");
    matchListings(ids, token)
      .then((results) => {
        if (!cancelled) onChange(new Set(results.filter((r) => r.qualified).map((r) => r.listing_id)));
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(`Couldn't check your qualifications. ${err.message}`);
        onChange(null);
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, idsKey, token, onChange]);

  return (
    <div className="cc-qualified-toggle">
      <input id={id} type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
      <label htmlFor={id}>Only show jobs I qualify for</label>
      {checking && <span className="cc-muted"> Checking…</span>}
      {error && (
        <span className="cc-error" role="alert">
          {" "}
          {error}
        </span>
      )}
    </div>
  );
}
