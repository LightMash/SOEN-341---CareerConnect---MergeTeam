# Static analysis reports (Sprint 4)

Tools: ruff (bugs/smells/style), bandit (security), ESLint (frontend). All run in CI
(job `static-analysis` in `.github/workflows/ci.yml`); raw output is uploaded as the
`static-analysis-reports` artifact on every run.

## Workflow
1. Save the baseline run's raw output in `baseline/` and write `report-01-baseline.md`.
2. Fix issues one rule/issue per commit; reference the report row in the message,
   e.g. `fix(bandit): B105 hard-coded secret (report-01 #3)`.
3. Re-run, save `report-02-after-fixes.md` with before/after counts.

## Report template

| # | Tool | Rule | File:line | Severity | Type (bug/vuln/smell) | Status | Fix commit |
|---|------|------|-----------|----------|-----------------------|--------|------------|
