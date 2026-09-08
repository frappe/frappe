# Code Review Guide

What maintainers check when they review a pull request to `frappe/frappe`. For reviewers, contributors and AI agents.

Contributor-side rules live in the [Pull Request Checklist](https://github.com/frappe/erpnext/wiki/Pull-Request-Checklist) and [Coding Standards](https://github.com/frappe/erpnext/wiki/Coding-Standards).

## Before reviewing

Check these first. Ask for the missing piece before reading the code.

- UI changes have before/after screenshots or a video. Ask again after every UI push.
- The bug reproduces on latest develop with the steps in the PR. If there are no steps, ask for a traceback or a minimal repro. If it cannot be reproduced, close for now.
- Branch is rebased with no merge commits or unrelated commits.
- Title and commits follow Conventional Commits.
- Description says what was broken, why, what changed and how to test, and matches the final diff.
- Read the other reviewers' comments and the linked issue before writing your own.

## What to look for

### Design

- Does this belong in the framework? App-specific fields, doctypes, roles or conditions belong in the app. The framework provides the hook; the app provides the behaviour.
- Non-framework features (print backends, spam filters, third-party integrations) go in a separate app.
- A new framework API ships together with at least one real use inside Frappe. No is temporary, yes is forever.
- Ask what problem the PR solves before judging how it solves it. Feature work and large refactors need agreement first.
- No new setting for behaviour one app or one user wants. Ship the sane default, or make it per-DocType through Customize Form. Make it configurable only when users would legitimately disagree.
- Do not extend surfaces the project is moving away from.
- The size of the change matches the size of the problem. Extend the existing feature rather than build a parallel one.

### Root cause

- A fix that makes an error disappear without explaining why it happened is not a fix. Find where the bad state comes from and fix it there, not at one call site.
- Deleting a guard, condition or method to make a symptom go away is not a fix. The check was protecting something.
- Read the commit that introduced the behaviour before changing it. Odd code is often intentional.
- Validation goes in `validate`, `on_trash` or `on_update`, not in one whitelisted caller. Bulk actions, the REST API and `doc.save()` skip a check that lives in one endpoint.
- If the same bug exists in a sibling (JS and Python, DocField and Custom Field, form and list and print), the fix is incomplete.

### Simplicity

- Before adding a field, flag, parameter, endpoint or patch, check whether an existing one already expresses the same thing. Two mechanisms for one meaning will disagree.
- Reuse `frappe.utils`, `frappe.ui`, the database API and the standard library before writing a helper. One implementation per piece of logic.
- Prefer the smallest correct change. Plain functions and `if` blocks; no inheritance towers, monkey-patching or global state unless proven necessary.
- Leftover code is a blocking finding: unused parameters, unreachable branches, no-op CSS, flags nothing reads, commented-out code.
- Functions take named arguments, not dict or kwargs bags. State goes on `doc.flags`, not `frappe.flags`. A function returns one shape.
- No hardcoded doctype names, `Administrator` checks, hosts or paths. Read hooks, defaults and config.
- Every new branch handles `None`, duplicates, submitted documents and deleted doctypes, and a new guard must not block the path the user takes to fix it.

### Backward compatibility

- Break established behaviour only when the cost of not breaking it is clearly higher. List who depends on it across frappe, erpnext, hrms and the other apps.
- Public functions, paths and parameters get a `deprecation_warning`, one major for apps to migrate, then removal.
- Defaults never flip. New behaviour is opt-in.
- Never repurpose or retype a field. Add a new one, migrate, hide the old one. New arguments go last with a default.
- Exports and report columns are an API.
- A new constraint or validation that existing rows would violate blocks `bench migrate`. Ship a patch or drop the constraint.
- Breaking changes use `fix!:` or `feat!:`, stay on develop, and land after the dependent app PR.
- Do not make a common workflow harder for regular users. Put the burden on system managers.

### Security

- Business logic and validation live on the server. The REST API, data import and server scripts never run client code.
- `ignore_permissions=True` and blanket role grants are not fixes. Use `check_permission`, `has_permission` and `only_for`, and give the user the right permission.
- Every whitelisted method checks permission before reading and takes identity from `frappe.session.user`, never from the client. Guest and security-critical endpoints restrict `methods`. Secrets are stored hashed and never returned.
- Escape at render time, per context. Never sanitise at storage; stripping loses data.
- A security claim needs a demonstrated bypass. Harden once in the shared layer, not per input. But any path that lets a normal user gain admin is blocked whatever the UX cost.
- Fail loudly. No blanket `try/except`, no `log_error` without a traceback, catch the specific exception.
- Never destroy data silently. Disable instead of delete, confirm bulk actions, no `ELSE NULL` in update queries.

### Performance

- Nothing lands in the hot path for everyone. Anything that runs on every request, save or desk boot is opt-in or free. Read from `frappe.boot` instead of calling the server on page load.
- Think in 100k rows. No `get_doc` in loops, no unindexed filters, no full-table sorts, no unbounded fetches.
- Work over a few seconds, third-party calls and bulk operations go to a background job. Patches use bulk updates and commit in batches.
- Performance changes come with numbers: profiler output, `EXPLAIN`, or bundle deltas, measured as a real user. No cache without a measured cost it removes.

### Database

- Use the highest-level API that does the job: ORM, then query builder, never hand-written SQL. Do not bypass `delete_doc` and controller hooks with `frappe.db.delete`.
- No `commit()` in document events. Side effects that must survive run `after_commit`.
- Convert inputs into query builder objects; never regex-check or rewrite generated SQL. MariaDB is the reference; DB-specific code lives in `frappe/database/<db>/`. Sorts that feed pagination are deterministic.
- Pick the right cache and prove invalidation. `site_cache` is per process and never invalidated.
- DocType JSON is changed through the UI, never by hand, and committed with a bumped `modified`. Patches only when data actually needs to move.

### UI

- Any CSS property that has a token (colour, font size and weight, spacing, radius, shadow, border, z-index) uses the `var(--*)` token, never a literal value. Reuse existing CSS classes; delete rules with no user. No inline styles or `!important`.
- Use `es-button` and `es-badge`, icons from `frappe.utils.icon()`, gray accents. New controls follow the sibling control.
- Defaults serve non-technical users. Labels say what happens, in short plain words, with no internal terms like "DocType".
- Bundle size is a budget. Features used by a minority load on first use.
- A button and dialog on the existing doctype beats a new doctype. A permission beats a setting.
- Confirm destructive actions. Only one primary button is visible on a page or dialog; secondary actions are not primary buttons. Keyboard keeps working. Any change marks the form dirty. Console stays clean.
- Client work is scoped to the instance, runs once, and cleans up its listeners. Client checks also work when the value is set programmatically.

### Code

- Comments explain why, never what. Keep one for a non-obvious workaround. No `console.log`, `print`, commented-out code or `var`.
- Names say what the thing does. Fieldname mirrors label. Checkbox names are positive.
- Annotate all parameters and the return type, or none. Compare dates with `getdate()`, checkboxes with `cint`. `None`, `""` and `0` are different.
- Translate whole sentences with `{0}` placeholders. Never build a translatable string from pieces. Do not translate fieldnames, file names or user-authored labels.
- No guards for states that cannot happen. Flat functions with early returns.
- Tests never leak into production code. No `if frappe.in_test`.

### Tests

- New behaviour and bug fixes ship with a test that fails without the fix. A test that only checks nothing raised, or asserts on generated SQL, proves nothing.
- Test through public interfaces as a real user, not Administrator. Permission tests use `get_list`, not `get_all`. Fixtures use `example.com`.
- Flaky tests are fixed, not disabled. Changed behaviour updates the existing tests.

## Verdict

- Any real ask means changes requested. Approve when there is none. "Ready with nits" is only for things you would not actually ask to change.
- Blocking, not a nit: a new crash or uncaught exception, leftover no-op code, the same bug in a sibling file, a missing `modified` bump, a missing permission check, a breaking change without `!` and a migration path.
- Before reporting a finding, confirm the symbol, string or class you name exists where you say it does. Cite a file and line you actually read.
- Bot findings (Greptile, Copilot, Semgrep) are reproduced and answered with evidence, not dismissed and not repeated blindly.

## Writing the review

- Comment on the exact line, with a suggestion block when the fix is a one-liner. The review body is for asks with no line, such as missing tests or a wrong title.
- One concern per comment, in short plain sentences. Say what is wrong and what to do instead. Show code when that is clearer than words.
- Back the ask with the issue, the docs or this guide.
