import { useCallback, useEffect, useState } from "react";
import RequirementList from "./RequirementList";
import StandingPanel from "./StandingPanel";
import { claimQualification, getStanding, matchListings } from "./matchingApi";
import type { MatchResult, Standing } from "./matchingApi";
import "./matching.css";

// Shown inside an expanded job card in the job seeker's feed: how the
// seeker's qualifications line up with the listing, and their standing.

export default function ListingMatchDetails({ jobId, token }: { jobId: number; token: string }) {
  const [match, setMatch] = useState<MatchResult | null>(null);
  const [standing, setStanding] = useState<Standing | null>(null);
  const [error, setError] = useState("");
  const [claimingKey, setClaimingKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [results, standingResult] = await Promise.all([matchListings([jobId], token), getStanding(jobId, token)]);
    return { match: results[0] ?? null, standing: standingResult };
  }, [jobId, token]);

  useEffect(() => {
    let cancelled = false;
    load()
      .then((data) => {
        if (cancelled) return;
        setMatch(data.match);
        setStanding(data.standing);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(`Couldn't load how you match this job. ${err.message}`);
      });
    return () => {
      cancelled = true;
    };
  }, [load]);

  async function claim(key: string) {
    setClaimingKey(key);
    setError("");
    try {
      await claimQualification(key, token);
      const data = await load();
      setMatch(data.match);
      setStanding(data.standing);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add it. Try again.");
    } finally {
      setClaimingKey(null);
    }
  }

  if (error) {
    return (
      <p className="cc-error" role="alert">
        {error}
      </p>
    );
  }
  if (!match || !standing) return <p className="cc-muted">Checking your qualifications…</p>;

  return (
    <div className="cc-match">
      <h4 className="cc-standing-title">
        Qualifications{" "}
        <span className={`cc-match-badge ${match.qualified ? "is-qualified" : "is-not-qualified"}`}>
          {match.qualified ? "✓ You qualify" : "✗ Not qualified yet"}
        </span>
      </h4>
      <RequirementList items={match.requirements} onClaim={claim} claimingKey={claimingKey} />
      {match.requirements.length > 0 && <StandingPanel standing={standing} />}
    </div>
  );
}
