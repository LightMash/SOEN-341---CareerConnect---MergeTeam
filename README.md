# CareerConnect

## Project description
CareerConnect is a web-based platform designed to help job seekers manage their job search activities. The system allows users to create profiles, upload and manage resumes, search for job opportunities, track submitted applications, and follow the progress of their application process. The platform aims to centralize job-search activities and help users stay organized throughout their career development journey. Primary users are **job seekers** and **recruiters**.

## Identified problem
Job seekers typically spread their job search across multiple disconnected tools — job boards, spreadsheets, email threads, and separate resume files — with no single place to track where they've applied, what stage each application is in, or which jobs they're actually qualified for. This makes it easy to lose track of deadlines, forget follow-ups, and waste time applying to roles that don't match their qualifications. On the other side, recruiters lack a simple, centralized way to post openings and see relevant candidates without relying on third-party platforms.

## Proposed solution
CareerConnect centralizes the entire job-search workflow in one platform: a single account lets a job seeker manage their profile and resumes, search and filter job postings, submit applications, and track each application's status (Applied, Interview, Offered, Rejected) from one dashboard. Recruiters get a straightforward way to post and manage job listings. On top of this core workflow, CareerConnect layers Generative-AI-assisted features — resume/job matching, and the original features described below — to reduce the manual effort involved in finding the right job and applying to it.

## Team members
- Diego / dc905
- Essam / Essamamiri
- Ethan / Eitanius
- Ismail / icherfa
- Mamadou / LightMash

## Technologies
**Backend:** Python, FastAPI, SQLAlchemy (ORM), Pydantic v2, PostgreSQL (hosted on Supabase), `python-jose` (JWT auth), `bcrypt` (password hashing), Uvicorn (dev server).

**Frontend:** React 19, TypeScript, Vite, React Router v7, native `fetch` for API calls.


## Setup instructions

**Prerequisites:** Python 3, Node.js/npm, and Git installed. You'll also need the shared Supabase `DATABASE_URL` from a teammate.

1. Clone the repository

2. Run the setup script (one-time, or after pulling changes to requirements.txt/package.json):
```bash
   cd "Sprint 1"
   ./setup.sh
```
3. Fill in `backend/.env` with the shared Supabase `DATABASE_URL` if setup.sh flagged it as missing.
4. Run both servers:
```bash
    cd "Sprint 1"
   ./run.sh
```
4. Once both servers are running, open the URL Vite prints in the terminal (usually `http://localhost:5173`).

## Proposed features
Core functionality required for the platform to work as a job-search and application-tracking tool:

- User registration, authentication, and profile management
- Resume upload and management
- Job posting management for recruiters
- Job search and filtering
- Job application submission
- Application status tracking (Applied, Interview, Offered, Rejected)
- Application history dashboard
- Notifications and reminders for application deadlines
- Saved jobs and favourites

## Original features
Beyond the core platform, the team is proposing the following Generative-AI-assisted and original features:

### 1. AI Job Study Partner *(up to change)*
The intent behind this feature: when a listing shows a qualification a user doesn't have, give them a concrete next step rather than a dead end. The current working proposal is **not** a tutoring/study feature, but a **pathfinding** feature — clicking a missing (red) qualification would either:

- open a search for how to obtain that qualification, or
- use the ai to surface a legitimate, local resource (e.g., linking a Quebec resident to the relevant school or government certification page for a specific requirement).

Possibility: whether it should attempt to "teach" missing skills directly, or stay in scope as a **router to existing, official resources** (courses, certifications, licenses, government sites). Formal certifications and licenses are outside what an AI can credibly issue, so the current lean is toward the latter — it would points users to the simplest legitimate path, rather than trying to replace the institutions that grant the qualification.

### 2. AI Resume/Job Matching
Rupert scans uploaded CVs and job listings, extracts qualifications as keywords, and matches job seekers to listings they're eligible for. This match is what powers the default filtered homepage.

### 3. Sign-in with Other Social Media
OAuth-based sign-in (e.g., Google, LinkedIn, etc.) as an alternative to traditional email/password registration.

### 4. Forgotten Password Mechanic
Standard secure password-reset flow (email verification, reset link/token, expiry handling).

### 5. AI Cover Letter Generator
Rupert automatically writes a tailored cover letter for each job application, using the user's resume and the specific listing's content — reducing one of the most repetitive and time-consuming parts of applying to jobs.

## GitHub repository
https://github.com/LightMash/SOEN-341---CareerConnect---MergeTeam

## Work plan
https://docs.google.com/spreadsheets/d/1NvdVNPcXiwHXQwLHTXiUjov4u6uQEXXQDxeHuQ1j4xc/edit?usp=sharing

