import type { User, Job } from "../../api";

// Sample jobs for the dashboard
import { sampleJobs } from "../../sampleJobs";

// CSS style
import '../../styles/jobs.css'

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

      {isSeeker ? (
        <section className="cc-section">
          <h2 className="cc-section-title">Job Listings</h2>
            <ul className="cc-jobs-list">
              {sampleJobs.map((job: Job) => (
                <li key={job.id} className="cc-job-card">
                  <h3>{job.title}</h3>
                  <p className="cc-card-meta">{job.company} | {job.location}</p>
                  <ul className="cc-chips">
                    <li className="cc-chip">{job.category}</li>
                    <li className="cc-chip">{job.employment_type}</li>
                    <li className="cc-chip">{job.work_from}</li>
                  </ul>
                </li>
              ))}
            </ul>
        </section>
      ) : (
        <section className="cc-section">
          <h2 className="cc-section-title">Recruiter Tools</h2>
        </section>
      )}
    </>
  );
}
