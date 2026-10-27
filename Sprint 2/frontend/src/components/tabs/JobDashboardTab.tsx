import { useEffect, useState } from "react";
import type { User, Job, JobFilters } from "../../api";
import { listJobs } from "../../api";

// CSS style
import "../../styles/jobs.css";

// Empty filter state, also used by the Clear button
const EMPTY_FILTERS: JobFilters = {
  q: "",
  location: "",
  category: "",
  job_type: "",
  work_from: "",
};

// How long to wait after the last keystroke before refetching (ms)
const DEBOUNCE_MS = 350;

// Formats the optional salary range, e.g. "$50,000 – $65,000"
function formatSalary(min: number | null, max: number | null): string | null {
  const fmt = (n: number) =>
    n.toLocaleString("en-CA", { style: "currency", currency: "CAD", maximumFractionDigits: 0 });
  if (min !== null && max !== null) return `${fmt(min)} – ${fmt(max)}`;
  if (min !== null) return `From ${fmt(min)}`;
  if (max !== null) return `Up to ${fmt(max)}`;
  return null;
}

// The default tab. Job seekers see the job listings (Sprint 2 job-search feature).
// Recruiters will see their tools here as well.
export default function JobDashboardTab({ user, token }: { user: User; token: string }) {
  const isSeeker = user.role === "job_seeker";

  // What the inputs show right now (updates on every keystroke)
  const [filters, setFilters] = useState<JobFilters>(EMPTY_FILTERS);
  // The filters actually sent to the API, lagging behind `filters` by DEBOUNCE_MS
  const [debouncedFilters, setDebouncedFilters] = useState<JobFilters>(EMPTY_FILTERS);

  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // Id of the card whose details are expanded (only one at a time)
  const [openId, setOpenId] = useState<number | null>(null);

  // Debounce: each change restarts the timer, so only the last value
  // after the user stops typing makes it through.
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedFilters(filters), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [filters]);

  // Fetch whenever the debounced filters change. `cancelled` drops responses
  // from older requests that finish after a newer one started.
  useEffect(() => {
    if (!isSeeker) return;
    let cancelled = false;
    setLoading(true);
    setError("");

    listJobs(debouncedFilters, token)
      .then((data) => {
        if (!cancelled) setJobs(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [debouncedFilters, token, isSeeker]);

  // One handler for every input/select, keyed by the filter name
  function updateFilter(key: keyof JobFilters, value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  // Clear skips the debounce since there's nothing to wait for
  function clearFilters() {
    setFilters(EMPTY_FILTERS);
    setDebouncedFilters(EMPTY_FILTERS);
  }

  const hasFilters = Object.values(filters).some((v) => v && v.trim());

  // Fragment (<>) instead of a wrapper <div>: the parent <main className="cc-main">
  // is a flex column with a gap, and fragments let this tab's header and
  // sections be its direct children so that spacing applies to them.
  return (
    <>
      <header className="cc-main-head">
        <div>
          <h1 className="cc-title">Job Dashboard</h1>
          <p className="cc-subtitle">
            {isSeeker
              ? "Browse and track opportunities."
              : "Your recruiter tools will live here."}
          </p>
        </div>
      </header>

      {isSeeker ? (
        <section className="cc-section">
          <h2 className="cc-section-title">Job Listings</h2>

          {/* Search bar + filters */}
          <div className="cc-job-filters">
            <input
              className="cc-input"
              type="search"
              placeholder="Search title, company, keywords…"
              aria-label="Search jobs"
              value={filters.q}
              onChange={(e) => updateFilter("q", e.target.value)}
            />
            <input
              className="cc-input"
              placeholder="Location"
              aria-label="Location"
              value={filters.location}
              onChange={(e) => updateFilter("location", e.target.value)}
            />
            <input
              className="cc-input"
              placeholder="Category"
              aria-label="Category"
              value={filters.category}
              onChange={(e) => updateFilter("category", e.target.value)}
            />
            <select
              className="cc-input"
              aria-label="Job type"
              value={filters.job_type}
              onChange={(e) => updateFilter("job_type", e.target.value)}
            >
              <option value="">Any type</option>
              <option value="Full-time">Full-time</option>
              <option value="Part-time">Part-time</option>
              <option value="Internship">Internship</option>
              <option value="Contract">Contract</option>
            </select>
            <select
              className="cc-input"
              aria-label="Work from"
              value={filters.work_from}
              onChange={(e) => updateFilter("work_from", e.target.value)}
            >
              <option value="">Any setting</option>
              <option value="On-site">On-site</option>
              <option value="Remote">Remote</option>
              <option value="Hybrid">Hybrid</option>
            </select>
            <button
              type="button"
              className="cc-upload-btn cc-btn-secondary"
              onClick={clearFilters}
              disabled={!hasFilters}
            >
              Clear
            </button>
          </div>

          {/* Status: loading, error, or empty results */}
          {loading && <p className="cc-muted">Loading jobs…</p>}
          {!loading && error && (
            <p className="cc-error" role="alert">
              {error}
            </p>
          )}
          {!loading && !error && jobs.length === 0 && (
            <p className="cc-muted">
              {hasFilters ? "No jobs match your filters." : "No jobs posted yet."}
            </p>
          )}

          {/* Listings: clicking "View details" expands the card in place */}
          {!loading && !error && jobs.length > 0 && (
            <ul className="cc-jobs-list">
              {jobs.map((job) => {
                const isOpen = openId === job.id;
                const salary = formatSalary(job.salary_min, job.salary_max);
                return (
                  <li key={job.id} className="cc-job-card">
                    <h3>{job.title}</h3>
                    <p className="cc-card-meta">{job.company} | {job.location}</p>
                    <ul className="cc-chips">
                      <li className="cc-chip">{job.category}</li>
                      <li className="cc-chip">{job.job_type}</li>
                      <li className="cc-chip">{job.work_from}</li>
                    </ul>

                    {isOpen && (
                      <div className="cc-job-details" id={`job-details-${job.id}`}>
                        {salary && <p><strong>Salary:</strong> {salary}</p>}
                        <p className="cc-muted">
                          Posted {new Date(job.created_at).toLocaleDateString("en-CA")}
                        </p>
                        {/* cc-prewrap keeps the recruiter's line breaks */}
                        <p className="cc-prewrap">{job.description}</p>
                      </div>
                    )}

                    <button
                      type="button"
                      className="cc-job-button"
                      aria-expanded={isOpen}
                      aria-controls={`job-details-${job.id}`}
                      onClick={() => setOpenId(isOpen ? null : job.id)}
                    >
                      {isOpen ? "Hide details" : "View details"}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      ) : (
        <section className="cc-section">
          <h2 className="cc-section-title">Recruiter Tools</h2>
          <div className="cc-soon">
            <p>Posting and managing jobs is coming soon.</p>
          </div>
        </section>
      )}
    </>
  );
}