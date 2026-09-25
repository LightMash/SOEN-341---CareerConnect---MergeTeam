# Merge Team

**We didn't just build another job board — we reinvented job hunting.**

Merge Team is a job-hunting platform built to strip away the friction of the modern job search. Instead of scrolling through hundreds of listings you're not qualified for, or staring at a blank page wondering how to write another cover letter, Merge Team surfaces the jobs you can *actually* apply for right now, tells you exactly what's missing when you can't, and automates the busywork in between. Our core purpose is simple: make job hunting as accessible and low-friction as possible.

## Table of Contents

- [Core Concept](#core-concept)
- [Meet Rupert](#meet-rupert)
- [Features](#features)
- [How the Qualification Matching Works](#how-the-qualification-matching-works)
- [Status](#status)
- [Team](#team)

## Core Concept

Most job sites make you do the filtering yourself: read a listing, compare it against your own resume in your head, decide if it's worth applying. Merge Team flips that. The **default homepage is pre-filtered** to only show job listings you are already qualified to apply for, based on an automated match between your CV and the listing's requirements. No more wasted applications, no more guesswork.

Users can still opt into broader views:

- **All Listings** — every open job posting, regardless of fit.
- **Unqualified Listings** *(planned)* — jobs you're close to qualifying for, so you know what to work toward.

Standard job-search tools are included as well: keyword search, and filters for job type (on-site/remote/hybrid), employment type (full-time/part-time/internship/contract), and more.

## Meet Rupert *(name TBD — pending team discussion)*

"Rupert" is a working name, not a finalized one. The idea is to make the AI feel like an approachable, professional personal job-finding agent rather than a generic "AI feature" — but the name itself still needs to be discussed and agreed on as a team. Until then, Rupert is used as a placeholder throughout this README and the codebase. Rupert (or whatever he ends up being called) handles:

- **Resume scanning** — reads an uploaded CV and extracts qualifications as structured keywords.
- **Listing analysis** — reads job postings (or manually tagged employer requirements) and extracts the qualifications they're looking for.
- **Matching** — compares job seeker keywords against listing keywords to determine eligibility.
- **Cover letter generation** — automatically drafts a tailored cover letter for each job a user applies to, based on their resume and the specific listing.
- **Qualification pathfinding** *(proposed, pending team discussion — see below)* — when a user is missing a qualification, Rupert helps them find the most direct route to acquiring it.

## Features

### 1. AI Job Study Partner *(needs team discussion)*
The intent behind this feature: when a listing shows a qualification a user doesn't have, give them a concrete next step rather than a dead end. The current working proposal is **not** a tutoring/study feature, but a **pathfinding** feature — clicking a missing (red) qualification would either:

- open a search for how to obtain that qualification, or
- use Rupert to surface a legitimate, local resource (e.g., linking a Quebec resident to the relevant school or government certification page for a specific requirement).

Open question for the team: whether Rupert should attempt to "teach" missing skills directly, or stay in scope as a **router to existing, official resources** (courses, certifications, licenses, government sites). Formal certifications and licenses are outside what an AI can credibly issue, so the current lean is toward the latter — Rupert points users to the simplest legitimate path, rather than trying to replace the institutions that grant the qualification.

### 2. AI Resume/Job Matching
Rupert scans uploaded CVs and job listings, extracts qualifications as keywords, and matches job seekers to listings they're eligible for. This match is what powers the default filtered homepage.

### 3. Sign-in with Other Social Media
OAuth-based sign-in (e.g., Google, LinkedIn, etc.) as an alternative to traditional email/password registration.

### 4. Forgotten Password Mechanic
Standard secure password-reset flow (email verification, reset link/token, expiry handling).

### 5. AI Cover Letter Generator
Rupert automatically writes a tailored cover letter for each job application, using the user's resume and the specific listing's content — reducing one of the most repetitive and time-consuming parts of applying to jobs.

## How the Qualification Matching Works

1. **Job seekers** upload a CV to their profile. Rupert scans it and tags the profile with qualifications (keywords).
2. **Employers** either manually input required qualifications (keywords) for a listing, or submit a traditional text listing that Rupert scans and auto-tags, the same way it does for CVs.
3. The system compares a user's qualification keywords against a listing's required keywords — effectively a **key-and-lock system**.
4. **Full match** → the listing appears on the user's default (pre-filtered) homepage.
5. **Partial match** → the listing is excluded from the default view, but individual qualifications are color-coded in the listing text:
   - 🟢 **Green** — user has this qualification.
   - 🔴 **Red** — user is missing this qualification.
6. Red (missing) qualifications are where the AI Job Study Partner / pathfinding feature is intended to help.

## Status

This is an active work-in-progress software engineering class project. The five user stories above represent our initial planned feature set — more features may be added as the project evolves. Feature 1 (AI Job Study Partner) is explicitly unfinalized and pending a team discussion on scope, and the AI agent's name ("Rupert") is a placeholder pending a separate team discussion.

## Team

Essam Amiri,
Mamadou Camara,
Ismail Cherfaoui,
Diego Chidiac,
Ethan Fadlon
