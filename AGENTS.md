# Agent instructions

Frappe is a web framework: Python backend, JavaScript desk UI, MariaDB or Postgres. ERPNext, HRMS, CRM and other apps are built on it, so every change here affects them.

## Reviewing a PR

Read [code_review.md](code_review.md) first and follow it in order: the checks before reviewing, what to look for, the verdict.

- No before/after screenshot or video for a UI change: ask for one before reviewing anything else.
- PR not based on `develop`: close it, unless the bug exists only on the stable branch.
- Any real ask means request changes. Do not hide a real finding under an approve.

## Writing code

- Target `develop`. Backports go through Mergify.
- Conventional Commits on the title and every commit.
- Business logic and validation on the server.
- Change DocType JSON through the UI, never by hand.
- No comments that narrate the code; keep comments that explain non-obvious workarounds.
- Run `pre-commit run --all-files` before pushing.
- Smallest correct change. Remove dead code and dead CSS you leave behind.
- Desk UI: `frappe.utils.icon()`, `es-button`, `es-badge`, design tokens, gray accents.
- Every user-facing string goes through `_()` or `__()`.
- New behaviour and bug fixes come with a test that runs as a normal user, with `example.com` test data.

## Never

- Add a field, flag, setting or endpoint when an existing one already does the job.
- Put ERPNext, CRM or Drive logic inside the framework.
- Use `ignore_permissions=True` or a blanket role grant to fix a workflow.
- Commit inside document events.
- Add work to every request or desk boot for a rare case.
- Refactor across the repo unless asked.
- Send automated or AI-generated changes without reviewing them yourself.
