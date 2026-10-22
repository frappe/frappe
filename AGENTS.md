# Agent instructions

Frappe is a web framework: Python backend, JavaScript desk UI, MariaDB or Postgres. ERPNext, HRMS, CRM and other apps are built on it, so every change here affects them.

Maintainers review every pull request against [code_review.md](code_review.md). Follow this file while you work, and check your diff against that one before you open the pull request.

## Before you write code

1. Confirm the problem still exists on latest `develop`. Run `git log -p` on the lines involved, and `git log -S '<expression>'` to find the commit that caused it. The code may be fixed already, dead (behind a condition that is always false), replaced by a newer code path, or different from the version in the report. If the bug no longer happens, stop and say so. Do not change code to match the report.
2. Reproduce it on a site, as a normal user, with the steps from the report. If you have no bench, say so in the pull request. Never write that you reproduced, tested or checked something you did not run.
3. Read the whole flow before you change either end: the JS caller, the whitelisted method, the controller and its hooks. A wrong value on the server usually comes from the client, and a wrong value on the client from the server. Find where the bad value is produced.
4. Look for what already exists. Grep `frappe.utils`, `frappe.ui`, `frappe.model`, the desk components and the CSS for a helper, control, class, field or setting that already does the job. Grep every function, CSS class, token and icon name you use before you use it. Never guess a name.
5. A new feature, setting, DocType, hook or API, or a large refactor, needs agreement in an issue first.

## Making the change

- Fix the cause, where the bad value is produced. Do not add a `try/except`, an `isinstance` check, an `if x:` guard or an `!important` where the error shows up. When one side sends a value the other side cannot use, find the contract between them (what the other callers send, what the code and its comments say each side expects) and fix the side that breaks it. If you cannot reach the cause, say so in the pull request.
- Grep the buggy expression across the repo and fix every copy: JS and Python, DocField and Custom Field, form, list, report and print, every caller of the function you change.
- Existing sites already have the bad data. When the bug wrote wrong rows or left orphan rows, add a patch to `patches.txt` that cleans them up.
- Before you remove a guard, override or fallback, read the commit that added it and prove every case it handled is gone.
- Grep the tests that call the function you changed, directly or through a wrapper such as a whitelisted method. Existing tests that rely on the old behaviour will fail, so update them in the same pull request. Never weaken a test to make your change pass: do not delete it, loosen an assertion, or move a case from rejected to accepted, unless the old behaviour is the bug. Then say so in the pull request.
- When you find dead code in the path, delete it. Do not build around it. Delete what your change leaves unused.
- Before you change a public function, whitelisted method, hook or JS API, grep its callers in frappe, erpnext and hrms. Add new arguments last, with a default. Never flip a default.
- Smallest correct diff. No reformatting, renames or moves in code you did not need to touch. One fix per pull request.
- No comments that narrate the code, the bug or your change ("Fix for #123", "now we also check ..."). The reasoning goes in the pull request description. Keep a short comment only for a non-obvious workaround. Some files already have long comments; do not copy that style.
- Business logic and validation on the server. Change DocType JSON through the UI, never by hand. Every user-facing string goes through `_()` or `__()`. Validation errors use `frappe.throw(msg, title=_(...))`.
- Desk UI: `frappe.utils.icon()`, `es-button`, `es-badge`, `var(--*)` tokens instead of literal values, gray accents, no inline styles, no `!important`.
- Tests: bug fixes and new behaviour come with a test that fails without the change. Run it as a normal user, not Administrator, with `example.com` data. Do not mock the function that decides the result. Presentation-only changes ship with a before and after screenshot instead; text or markup a caller depends on is behaviour and still needs a test.

## Before you open the pull request

- Run `pre-commit run --files <changed files>`, and `bench --site <site> run-tests --module <module>` for the code you touched. After you push, fix every CI failure your change causes.
- Review your diff against [code_review.md](code_review.md), section by section, and fix what you find.
- Read the final diff line by line: no debug code, no unrelated files.
- List every comment line your diff adds (`git diff develop -U0 | grep -E '^\+\s*(#|//|/\*|\*)'`). Delete each one that says what the code does, what was wrong before, or why you changed it. That belongs in the pull request. Keep a docstring that tells callers something the signature does not, such as a limit or a side effect.
- Target `develop`. Backports go through Mergify. The title and every commit use [Conventional Commits](https://www.conventionalcommits.org/): `fix:`, `feat:`, `refactor:`, `perf:`, `chore:`, and `!` for a breaking change.

## The pull request description

A reviewer should know in twenty seconds what changed and how to check it. Fill in the template:

```
<one line: what was broken, as a user sees it>

- <what changed, as a user sees it>
- <how you tested it: the steps or the test you ran, or "not run">

Closes #<issue>
```

- A UI change needs a before and after screenshot or a short video.
- Each bullet is one sentence. No sections like Problem, Root cause, Fix or Why. No checklist of steps you did not run. Do not paste the diff or name every file you touched.
- Keep the description in sync with the final diff.

## Never

- Claim you ran, reproduced or tested something you did not.
- Add a field, flag, setting or endpoint when an existing one already does the job.
- Put ERPNext, CRM or Drive logic inside the framework.
- Use `ignore_permissions=True` or a blanket role grant to fix a workflow.
- Commit inside document events.
- Add work to every request or desk boot for a rare case.
- Refactor across the repo unless asked.
- Send automated or AI-generated changes without reviewing them yourself.

## Reviewing a pull request

Read [code_review.md](code_review.md) first and follow it in order: the checks before reviewing, what to look for, the verdict.

- No before/after screenshot or video for a UI change: ask for one before reviewing anything else.
- Pull request not based on `develop`: close it, unless the bug exists only on the stable branch.
- Any real ask means request changes. Do not hide a real finding under an approve.

## Desk v2 work

These are the standards for **desk v2 work** — `frontend/`, `ui/`, `frappe/shell/` and the
DocTypes those add. They are not a claim over the rest of `frappe`, whose code was written
under different conventions and is not swept to match.

A desk v2 pull request is based on `desk-v2`, not `develop`. The review rule above that
closes a pull request not based on `develop` does not apply to it.

Layer-specific rules live next to the layer and take precedence on their own ground:
[`frontend/PHILOSOPHY.md`](./frontend/PHILOSOPHY.md) (`DP1`-`DP4`),
[`ui/PHILOSOPHY.md`](./ui/PHILOSOPHY.md) (`FP1`-`FP3`), and the operational notes in
[`frontend/CLAUDE.md`](./frontend/CLAUDE.md) and [`ui/CLAUDE.md`](./ui/CLAUDE.md).
The layers, the concepts each keeps and the main flows are in
[`frontend/ARCHITECTURE.md`](./frontend/ARCHITECTURE.md). A new concept or a new edge
between layers needs a ruling, and the same PR updates it.

### Comments

**A comment earns its place only where the code cannot speak for itself**: a one-line note
on what the file does, and a constraint a reader would otherwise undo — a framework quirk,
a build-time gotcha, a paint-order trap.

Never narrate the next line, restate a name, explain a feature, or record history and
rationale. Three hard limits, so this stays a rule and not a judgement call:

- **Two lines maximum.** A third line means it is an explanation. Put it in the commit
  message.
- **One summary line per docstring.** No rationale paragraphs, no "why not X".
- **No commented-out code.**

Watch for the phrase **"rather than"**. It is the signature of justifying a choice against
an alternative you did not take, and that argument belongs in the commit message or the
ticket, not in the file.

A comment carries no ticket number. The constraint is the useful half; the citation ages
badly and sends the reader somewhere the code cannot follow.

**What this keeps.** A note like "freezing this instead of proxying it makes the object
non-extensible, so Vue's `reactive()` hands back the raw object and `meta` stops being
deeply reactive" is exactly the case for a comment: a reader would otherwise undo it. Cut
to the constraint and drop the history around it.

**Where a constraint is already written in a layer's `CLAUDE.md`**, the code does not
repeat it. One line naming the behaviour is enough.

### DocType field descriptions

A field's `description` is rendered as a paragraph under the input in the desk form, so it
is user-facing text. **One line, roughly 80 characters**, saying what the field holds and
any constraint on its value. Blank where the label already says it. The reasoning behind a
field's design belongs in its ticket.

### Shape

- Clean over clever. Object-oriented where the domain has objects.
- One job per function and per file. Split a file when it holds two concepts, not when it is long.
- Main function first, helpers below it in call order.
- No abbreviations. Prefer a standard API to a hand-rolled one.
- Logic two pages share belongs in a module under `composables/` or `data/`, not in both.
- Build the minimum that works, then iterate. Add a dependency only when it is required.

### Before you close a ticket

Run `/quality-code-review` **in a fresh subagent**, never in the session that wrote the
diff. Give it only the diff range, the checklist, this file, the layer's `CLAUDE.md`, and
the ticket's question with the rulings it must not re-open; not the session's reasoning.
The brief also asks four fixed questions, from the
[Guardrails](./frontend/ARCHITECTURE.md#guardrails) of `frontend/ARCHITECTURE.md`:

1. Does this PR add a second way to do a job that one mechanism already does?
2. Does it add a timing guard: a counter, a debounce, a gate or a fetch-once flag?
3. Does it add a DocType, a route, a store or a lifecycle event that is not in the concept tables?
4. Can this be done with fewer concepts or less code?

For a build PR, the reviewer also checks the six-field
[cost line](./frontend/ARCHITECTURE.md#guardrails) in the PR description.
Answer every finding, and close one that contradicts a ruling with the ruling. Then read
your diff against the comment rule above. For a change that is comments only, `.github/helper/comment_equivalence.py` proves it: it strips
comments from both revisions and asserts the remaining code is identical.

```bash
python .github/helper/comment_equivalence.py upstream/desk-v2 HEAD
python .github/helper/comment_equivalence.py --self-test
```

Two things it does not claim. It ignores blank lines and trailing whitespace **outside**
string literals, which cannot change behaviour in either language; inside a docstring or a
template literal both are content, and a change to either is reported. And it does not
prove a docstring *removal* is safe — a docstring is a runtime value in Python, so
anything reading `__doc__` changes behaviour. `--ignore-docstrings` compares the parsed
code with every docstring dropped, so the two revisions differ only in docstrings and
formatting; the test suites remain the proof that moving them was safe.
