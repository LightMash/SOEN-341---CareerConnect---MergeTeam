# Team Process Definition

## Workflow

We manage all our work through the GitHub Project board linked to our repo. Every piece of work, whether it's a user story or a smaller task, starts as a GitHub Issue, and it moves across the board as we work on it. All members are responsible for moving their own issues.

Our board has five columns:

- **Backlog:** Every new issue starts here. These are things we know we need to do but haven't planned or fully defined yet.
- **Ready:** An issue moves here once it meets our Definition of Ready. It has a clear description, acceptance criteria, labels, and an estimate. Only issues in Ready can be picked up.
- **In Progress:** When someone starts working on an issue, they assign themselves, move it here, and create a feature branch for it. We try to keep only one or two issues in progress per person at a time so things don't pile up half-finished.
- **In Review:** Once the work is pushed and a pull request is open, the issue moves here. It stays here until another team member reviews and approves the PR.
- **Done:** After the PR is approved and merged into `main`, and the issue meets our Definition of Done, it gets moved to Done and closed.

If someone gets blocked, they add a "blocked" label to the issue and mention it in the group chat so we can sort it out quickly instead of waiting for the next meeting. We also go over the board together at our team meetings and weekly lab check-ins to see what's moving and what's stuck.

## Branching Strategy

### Main branch
`main` always has working code. Nobody commits to it directly. Changes only get in through a pull request.

### Current approach: one branch per member
At the start of the project, each team member worked on their own branch named after them (`Essam`, `Diego`, `Ethan`, `Ismail`). This was simple to set up, but it gets messy when two people work on the same feature or when a branch falls behind `main`.

### Moving to: one branch per feature
We are switching to feature branches. Each branch is for one feature and is named after it, for example `Dashboard`. New feature branches are created from the latest `main`. Once the feature is merged into `main`, the branch can be deleted.

### Keeping branches up to date
Before starting work and before opening a pull request, pull the latest `main` into your branch:

git pull origin main

This way conflicts are small and get fixed early instead of piling up.

## Pull Request Process

All changes go into `main` through a pull request. `main` is protected on GitHub, so a pull request can't be merged until it gets at least one approval from another team member.

### Before opening a pull request
1. Commit and push your work to your branch.
2. Pull the latest `main` into your branch (`git pull origin main`).
3. If there are conflicts, fix them, commit, and push again.

### Opening the pull request
1. On GitHub, open a pull request from your branch into `main`.
2. Write a short description that includes:
   - What changed
   - Anything that isn't finished yet
   - How to test it
3. Request at least one teammate as a reviewer, and let them know in the group chat.

### After review
- If the reviewer asks for changes, push the fixes to the same branch. The pull request updates on its own.
- Once the pull request is approved, the author merges it into `main` and deletes the branch if it was a feature branch.

## Code Review Process

Every pull request needs at least one approval before it can be merged. The reviewer has to be someone other than the author (GitHub doesn't let you approve your own pull request).

### What the reviewer checks
- The feature works as described in the pull request (run it locally if the change affects how the app works)
- It doesn't break anything that already worked
- Only files related to the change were modified
- No secrets are committed (like `.env` files, API keys or passwords)
- The code is readable and there's no leftover test or debug code

### Giving feedback
Reviews are done on GitHub, in the "Files changed" tab of the pull request. The reviewer can comment on specific lines, then submit the review as one of:
- **Approve**: everything looks good and it can be merged
- **Request changes**: something needs to be fixed before merging
- **Comment**: questions or suggestions that don't block merging

Feedback should be about the code, and explain why something should change.

### After feedback
The author pushes the fixes to the same branch and replies to the comments. The reviewer checks the changes and approves once everything is resolved.

## Definition of Ready

A user story is ready to be worked on when:

- It is created as a GitHub Issue and written in the format "As a [type of user], I want [goal] so that [reason]"
- It has clear acceptance criteria that describe when the story is complete
- It has a priority (High, Medium or Low) and the right labels
- It has an effort estimate
- It is broken down into tasks, and each task is assigned to a team member
- It is small enough to be finished within one sprint
- Any dependencies on other stories are identified (for example, resume upload depends on login working)

If a story doesn't meet all of these, it goes back to the backlog to be refined before anyone starts on it.

## Definition of Done

A user story is done when:

- All of its acceptance criteria are met
- All of its tasks are completed
- The code has been tested and works as expected
- It went through the pull request process and got at least one approval
- It is merged into `main`, and the app still runs correctly after the merge
- No secrets are committed (like `.env` files, API keys or passwords)
- Documentation is updated if needed (for example, the README if setup steps changed)
- Any AI use for the story is recorded in the AI Usage Log
- The GitHub Issue is closed

If any of these aren't met, the story isn't done and it carries over to the next sprint.




