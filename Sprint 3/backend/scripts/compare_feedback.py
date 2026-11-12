"""
Dev tool: runs the real AI resume feedback outside the web app and
prints how each request went: score, number of suggestions, time taken and
which Gemini model answered.

Useful to check prompt changes, compare general vs job-tailored feedback,
or tell a Gemini outage apart from a bug in our code.

  - Calls the REAL Gemini API: every request uses free-tier quota.
  - Reads the database in .env (the shared one, usually) but never writes.
  - Not a test: pytest only collects test_*.py, so CI never runs it.

Usage, from backend/ with the venv active:
    python -m scripts.compare_feedback 17             # resume 17, general feedback only
    python -m scripts.compare_feedback 17 5 12        # ...plus tailored to jobs 5 and 12
    python -m scripts.compare_feedback 17 --all-jobs  # ...plus every job (many API calls!)
"""

import argparse
import time

from dotenv import load_dotenv

load_dotenv()  # before the imports below: database.py reads DATABASE_URL on import

from database import SessionLocal  # noqa: E402
from models import Job, Resume  # noqa: E402
from schemas.resume_feedback import AIFeedback  # noqa: E402
from services.ai_client import AIServiceError, generate_json_with_model  # noqa: E402
from services.resume_feedback import SYSTEM_INSTRUCTION, build_prompt, mark_applicable  # noqa: E402
from services.resume_parser import ResumeParseError, extract_text  # noqa: E402


def run(label: str, resume_text: str, job: Job | None = None) -> None:
    prompt = build_prompt(resume_text, job)
    print(f"\n--- {label} ({len(prompt)} characters sent) ---")
    start = time.time()
    try:
        feedback, model = generate_json_with_model(prompt, AIFeedback, system_instruction=SYSTEM_INSTRUCTION)
    except AIServiceError as exc:
        print(f"FAILED after {time.time() - start:.1f}s: {exc}")
        return

    suggestions = mark_applicable(feedback, resume_text)
    applicable = sum(s["can_apply"] for s in suggestions)
    print(
        f"OK in {time.time() - start:.1f}s with {model}: score {feedback.overall_score}, "
        f"{len(suggestions)} suggestions ({applicable} quote the resume exactly)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("resume_id", type=int)
    parser.add_argument("job_ids", type=int, nargs="*", help="jobs to tailor the feedback to")
    parser.add_argument("--all-jobs", action="store_true", help="tailor to every job in the database")
    parser.add_argument("--show-text", action="store_true", help="print the resume text the AI receives")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        resume = db.query(Resume).filter(Resume.id == args.resume_id).first()
        if not resume:
            raise SystemExit(f"No resume with id {args.resume_id}.")
        try:
            resume_text = extract_text(resume.filepath)
        except (ResumeParseError, FileNotFoundError) as exc:
            raise SystemExit(f"Can't read resume {resume.id}: {exc}")

        print(f"Resume {resume.id} ({resume.filename}): {len(resume_text)} characters of text")
        if args.show_text:
            print(resume_text)

        run("general feedback", resume_text)

        query = db.query(Job).order_by(Job.id)
        if not args.all_jobs:
            query = query.filter(Job.id.in_(args.job_ids or [-1]))
        for job in query.all():
            run(f"tailored to job {job.id}: {job.title} at {job.company}", resume_text, job)
    finally:
        db.close()


if __name__ == "__main__":
    main()
