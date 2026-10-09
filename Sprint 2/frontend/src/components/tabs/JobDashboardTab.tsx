import type { User } from "../../api";

// The default tab. For now it is the same placeholder the old dashboard
// showed; job listings, search and filters (Sprint 2 job-search feature) get
// built inside this component, so nothing else has to change when they land.
export default function JobDashboardTab({ user }: { user: User }) {
  const isSeeker = user.role === "job_seeker";

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

      <section className="cc-soon">
        <h2 className="cc-section-title">
          {isSeeker ? "Job listings are on the way" : "Recruiter tools are on the way"}
        </h2>
        <p>
          {isSeeker
            ? "Search, filters and job details will show up here."
            : "Posting jobs and finding candidates will show up here in a later sprint."}
        </p>
      </section>
    </>
  );
}
