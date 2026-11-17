import type { Standing } from "./matchingApi";

// "Your standing" for one listing. This compares listed qualifications only;
// it is NOT a hiring prediction, and the note at the bottom always says so.

function asPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatAsOf(iso: string): string {
  // The backend sends naive UTC timestamps.
  const date = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleString("en-CA", { dateStyle: "medium", timeStyle: "short" });
}

function applicantCount(n: number): string {
  return n === 1 ? "1 other qualified applicant" : `${n} other qualified applicants`;
}

export default function StandingPanel({ standing }: { standing: Standing }) {
  const usesPercentile = standing.status === "percentile";
  const ranked = usesPercentile || standing.status === "fraction";
  const formatValue = (v: number) => (usesPercentile ? `${v}%` : asPercent(v));

  return (
    <section className="cc-standing" aria-label="Your standing">
      <h4 className="cc-standing-title">Your standing</h4>

      {standing.status === "not_qualified" && (
        <div>
          <p className="cc-standing-headline">No standing yet</p>
          <p className="cc-muted">These required qualifications aren't on your profile yet:</p>
          <ul className="cc-standing-list">
            {standing.missing.map((m) => (
              <li key={m.key}>
                {m.name}
                {m.status === "possible" && m.possible_name && (
                  <span className="cc-muted"> (possible match: “{m.possible_name}”)</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {standing.status === "equal_on_paper" && (
        <p className="cc-standing-headline">{standing.message}.</p>
      )}

      {usesPercentile && standing.percentile !== null && (
        <div>
          <p className="cc-standing-headline">
            <span className="cc-standing-label">{standing.label}</span> · Ahead of {standing.percentile}% of qualified
            applicants
          </p>
        </div>
      )}

      {standing.status === "fraction" && standing.fraction !== null && (
        <div>
          <p className="cc-standing-headline">
            <span className="cc-standing-label">{standing.label}</span> · You have {asPercent(standing.fraction)} of
            the bonus points this listing offers
          </p>
          <p className="cc-muted">Not enough applicants yet to compare.</p>
        </div>
      )}

      <p className="cc-muted">
        {applicantCount(standing.other_applicants)} · as of {formatAsOf(standing.as_of)}
      </p>

      {ranked && standing.breakdown.length > 0 && (
        <table className="cc-standing-table">
          <caption className="cc-visually-hidden">Bonus qualifications</caption>
          <thead>
            <tr>
              <th scope="col">Bonus qualification</th>
              <th scope="col">Weight</th>
              <th scope="col">You</th>
              {usesPercentile && <th scope="col">Applicants with it</th>}
            </tr>
          </thead>
          <tbody>
            {standing.breakdown.map((row) => (
              <tr key={row.key}>
                <th scope="row">
                  {row.name}
                  {row.highlight && <span className="cc-standing-highlight">{row.highlight}</span>}
                </th>
                <td>{row.weight}</td>
                <td>{row.has ? "✓ Have it" : "— Don't have it"}</td>
                {usesPercentile && <td>{row.share === null ? "—" : asPercent(row.share)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {ranked && standing.suggestions.length > 0 && (
        <div>
          <p className="cc-standing-subtitle">What would help most</p>
          <ul className="cc-standing-list">
            {standing.suggestions.map((s) => (
              <li key={s.key}>
                Adding <strong>{s.name}</strong> would take you from {formatValue(s.current)} to{" "}
                {formatValue(s.new)}
                {usesPercentile ? "" : " of the bonus points"}.
              </li>
            ))}
          </ul>
        </div>
      )}

      {standing.profile_nudge && <p className="cc-standing-nudge">{standing.profile_nudge}</p>}

      <p className="cc-standing-note">{standing.note}</p>
    </section>
  );
}
