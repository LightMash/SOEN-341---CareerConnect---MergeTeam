# AI Usage Log - Sprint 1: Ismail Cherfaoui

## Task 1.1: Define 10 User Stories Using AI
**Purpose of AI use:** Brainstorming and requirements elicitation

**Chat link:** Claude Opus 5.5 (High): https://claude.ai/share/1fa29e2e-29fd-4e3e-8257-9f5f1f0984f7 
>See appendix A for the 10 user stories.

**AI suggested content:** Claude generated 10 user stories for job seekers and recruiters. Each story has a priority level and is broken down into three subtasks.

**Validation:** The user stories were compared against the required features list in the Sprint 1 specifications document.

**Decision:** Accepted.

**Reflection:** The generated user stories were good and covered the core features for the project, but there are very few recruiter user stories (2/10). We will address this by coming up with more user stories, including additional recruiter features.

**Responsible person:** Ismail Cherfaoui

<!-- TEMPLATE FOR TASKS -->
<!-- 
## Task X.X: 
**Purpose of AI use:** 

**Chat link:**
>See appendix A for the 10 user stories.

**AI-Suggested content:** 

**Validation:**

**Decision:**

**Reflection:**

**Responsible person:** Ismail Cherfaoui
-->

# Appendix

## A - Task 1.1: Define 10 User Stories Using AI


### CareerConnect User Stories

**US-01: Account registration and login**

As a job seeker, I want to create an account and log in securely so that I can access platform features and keep my job search data private.
- Priority: High
- Task 1.1: Design database schema for user account data, including a role field (job seeker/recruiter).
- Task 1.2: Implement authentication API (signup, login, logout endpoints with password hashing and session/token handling).
- Task 1.3: Build registration and login UI forms with input validation and error messages.

**US-02: Job seeker profile management**

As a job seeker, I want to create and edit my profile so that recruiters can see my background, skills, and contact information.
- Priority: Medium
- Task 2.1: Design database schema for profile data (education, experience, skills, contact info).
- Task 2.2: Implement profile API endpoints (create, read, update).
- Task 2.3: Build profile view and edit pages in the UI.

**US-03: Resume upload and management**

As a job seeker, I want to upload, replace, and delete my resumes so that I can keep up-to-date versions ready for different applications.
- Priority: High
- Task 3.1: Set up file storage and define accepted formats and size limits (e.g. PDF, DOCX).
- Task 3.2: Implement resume API endpoints (upload, list, download, delete) linked to the user account.
- Task 3.3: Build resume management UI showing uploaded files with upload date and actions.

**US-04: Job posting management**

As a recruiter, I want to create, edit, and close job postings so that job seekers can find and apply to my open positions.
- Priority: High
- Task 4.1: Design database schema for job postings (title, company, location, type, description, deadline, status).
- Task 4.2: Implement job posting API endpoints (create, update, close, delete) restricted to recruiter accounts.
- Task 4.3: Build recruiter UI for managing postings (form and list of the recruiter's own postings).

**US-05: Job search and filtering**

As a job seeker, I want to search for jobs by keyword and filter by location, job type, and posting date so that I can quickly find opportunities relevant to me.
- Priority: High
- Task 5.1: Implement search API endpoint with keyword matching and filter/query parameters.
- Task 5.2: Add database indexing on commonly searched fields to keep queries fast.
- Task 5.3: Build search page UI with search bar, filter controls, and paginated results.

**US-06: Job application submission**

As a job seeker, I want to apply to a job posting by selecting one of my resumes so that I can submit applications directly through the platform.
- Priority: High
- Task 6.1: Design database schema for applications (job, applicant, selected resume, submission date, status).
- Task 6.2: Implement application submission API endpoint, preventing duplicate applications to the same posting.
- Task 6.3: Build apply flow in the UI (resume selection, confirmation, success message).

**US-07: Application status updates**

As a recruiter, I want to update the status of each application (Applied, Interview, Offered, Rejected) so that applicants know where they stand in the hiring process.
- Priority: Medium
- Task 7.1: Implement API endpoint for updating application status, restricted to the recruiter who owns the posting.
- Task 7.2: Build recruiter UI listing applicants per posting with a status selector.
- Task 7.3: Record status change history with timestamps.

**US-08: Application history dashboard**

As a job seeker, I want a dashboard showing all my submitted applications and their current status so that I can track my progress in one place.
- Priority: Medium
- Task 8.1: Implement API endpoint returning the user's applications with job details and current status.
- Task 8.2: Build dashboard UI with application list, status indicators, and sorting/filtering by status.
- Task 8.3: Add summary counts per status (e.g. number of interviews, offers).

**US-09: Deadline notifications and reminders**

As a job seeker, I want to receive reminders before application deadlines of jobs I'm interested in so that I don't miss opportunities.
- Priority: Low
- Task 9.1: Design notification data model (recipient, type, message, read/unread, date).
- Task 9.2: Implement scheduled job that generates reminders for upcoming deadlines of saved jobs.
- Task 9.3: Build in-app notification panel with unread indicator and mark-as-read action.

**US-10: Saved jobs and favourites**

As a job seeker, I want to save job postings to a favourites list so that I can revisit and apply to them later.
- Priority: Low
- Task 10.1: Design database schema linking users to saved job postings.
- Task 10.2: Implement API endpoints to save, unsave, and list saved jobs.
- Task 10.3: Add save/unsave button to job listings and build a saved jobs page.
