# Frappe Framework: Code Review Guide

What maintainers check when they review a pull request to `frappe/frappe`, collected from their review comments. For reviewers, contributors and AI agents.

Read the Workflow section before every review. Rules are numbered so you can point to them in a comment (`R8`). If a rule gives a wrong answer in a real case, change the rule here instead of ignoring it.

Contributor-side rules live in the [Pull Request Checklist](https://github.com/frappe/erpnext/wiki/Pull-Request-Checklist) and [Coding Standards](https://github.com/frappe/erpnext/wiki/Coding-Standards).

---

## Workflow

### Read first

- Read the PR body and every comment. Maintainers often raise PRs on behalf of contributors ("raised on behalf of @x"). That person is the author you talk to.
- Read other maintainers' comments. Do not repeat them. Check whether earlier asks were addressed.
- Read the linked issue and check the PR fixes what it describes.

### Gates

Stop at the first failing gate and ask for it. Do not review code behind a failing gate.

1. Base branch is `develop`. A hotfix branch is fine only when the bug does not exist on develop. `version-N` is always wrong.
2. UI change has before/after screenshots or a video with real data. Anything a user sees counts: desk JS, Vue, SCSS, HTML, print formats, web pages, dialogs, icons. No media, no review. Ask again after every UI push.
3. The bug reproduces on latest develop with the PR's own steps. No steps: ask for a text traceback, the failing input or the minimal query. Cannot reproduce: close for now. Already fixed: close with the commit.
4. Branch is rebased, with no merge commits and no foreign commits.
5. Pre-commit is green. A reformatted file is not reviewable. Do not list files; give the command:
   ```bash
   pip install pre-commit && pre-commit run --all-files
   ```
6. Title and every commit follow Conventional Commits. The title is what gets squash-merged. `feat:` PRs carry `no-docs` or a docs link. `fixes #N` only if the issue is really fixed.
7. Description says what was broken, why, what changed and how to test. It matches the final diff.

### Review steps

Say which steps found nothing. Steps 2, 3 and 4 are the ones most often skipped.

1. Root cause. Find where the bad state comes from. If there is one writer, the fix undoes that writer. If the same failure fires later in the flow, the symptom moved. Read the commit that introduced the behaviour before accepting a change to it.
2. Should this exist in this shape. For every new field, flag, param, endpoint, setting or status: list the existing values next to it. If they already express the thing, the new one is redundant. Try the contradicting combination (old value says X, new flag says Y). `depends_on` only hides a field; a stale value still applies. A new status needs every abnormal exit covered.
3. Residue. Dead code, no-op CSS, orphan flags, classes, callers, tests, junk rows. Grep before calling a CSS rule a no-op. Residue is blocking.
4. Incomplete fix. Grep the buggy expression across the repo. Sibling files with the same bug (JS vs Python, DocField vs Custom Field vs Customize Form Field, MariaDB vs Postgres, form vs grid vs list vs print) make the fix incomplete. Check the sibling is reachable first.
5. Correctness and security. `None`, empty, `0`, `"0"`, negative, huge; docstatus 0, 1, 2; permissions; multi-site; translations; both databases. Every whitelisted method checks permission before reading and takes identity from `frappe.session.user`. Every new throw leaves the user a way out. Existing records keep working.
6. Conventions. DocType JSON edited through the UI with a bumped `modified`. `frappe.throw` with a title. `_()` / `__()` on user-facing strings. No comments, `console.log`, `print`, commented-out code, `var`. Desk UI uses `frappe.utils.icon()`, `es-button`, `es-badge`, design tokens, gray accents, no duplicate CSS. Fixtures use `example.com`. New server functions have tests.
7. CI. Name the failing check. Test failures block. Semgrep on unchanged code, the docs check and the dependency check do not block on their own.

Before reporting any finding, grep the exact symbol, string or class you name, in the repo and in the diff. If it is not there, drop it. Cite a file:line you read. One true sentence per finding. Bot findings (Greptile, Copilot, Semgrep) are reproduced on the branch and answered with facts.

### Verdict

Any real ask means changes requested. Ready with nits is only for things you would not actually ask to change. Send to a maintainer when the answer is in the Unsettled section or is a product call.

Blocking, not a nit: a new crash, blank screen or uncaught exception; leftover no-op code; a sibling file with the same bug; a missing `modified` bump; a missing permission check on a new endpoint; a stuck status; a breaking change without `!` and a migration path.

Do not downgrade a finding to approve. Do not upgrade a style nit to look thorough.

```
PR #N: <title>
Verdict: READY | CHANGES REQUESTED | NEEDS HUMAN JUDGMENT
Prior review: none | addressed | partly (what remains)
Rationale: up to 3 sentences
Findings:
  - blocking | nit, file:line, the one-sentence claim, the ask (rule ID), replacement text if one-line
Steps that found nothing: <numbers>
Repro: snippet that shows the bug on develop, or "UI-only"
```

### Writing the review

- Inline comments on the exact line, with a ` ```suggestion ` block when the fix is one line. The body is only for asks with no line (add tests, fix the title, add a video). Never write "see inline".
- `@handle` once, in the first comment, then ask: "@user, could you please …".
- One concern per comment. One to three short sentences. Plain words a non-native speaker reads once.
- For "do X instead", show X as a one-line code example.
- Cite the rule ID. Link the issue or docs when they exist.
- No preamble, praise, thanks, summary, signature or emoji.
- `REQUEST_CHANGES` when asks exist, `APPROVE` when none. `COMMENT` only on a PR you created yourself, because GitHub blocks the other two there.
- No AI attribution in reviews, commits or PR bodies.
- Answer every bot finding: confirm with a line reference or reject with a reason.

Example:

> @author, could you please move this check into `validate()`? List view bulk delete and `frappe.client.delete` skip it right now (R12).
>
> ```suggestion
> def validate(self):
>     self.validate_unique_route()
> ```

---

## Scope

### R1. No app-specific code in the framework
Frappe must behave the same for every app. Do not add a field, doctype, role or `if doctype == "Sales Invoice"` branch that only ERPNext, CRM, HRMS or Drive needs. Add a hook in the framework and let the app implement it in its own code.
Why: the framework cannot see how apps use it. A special case for one app breaks silently when that app changes.
Exception: something generic that every app could use may move from an app into the framework.

```python
# Bad: framework code checks an ERPNext doctype
if doc.doctype == "Sales Invoice" and doc.is_return:
    reverse_stock(doc)

# Good: framework offers a hook, ERPNext implements it in its hooks.py
for method in frappe.get_hooks("on_return_document"):
    frappe.call(method, doc=doc)
```

### R2. Non-framework features go in a separate app; framework features need a user
Print backends, spam filters, third-party integrations and similar live in an app that hooks in. A new framework API ships together with at least one real use inside Frappe.
Why: no is temporary, yes is forever. Plumbing without a consumer rots.

### R3. Ask for the use case before reading the code
If the PR does not state a user-facing problem, ask what the author is trying to do. Feature work and big refactors need a nod first (an issue or a discussion). Refactors of critical areas (caching, database APIs, `Document`) are done by core maintainers.
Why: reviewing a mechanism for a problem nobody has wastes both sides' time.
Exception: a small, clearly useful fix with no ticket still merges.

### R4. No new setting for niche behaviour
No System Settings switch, config key or checkbox for behaviour one app or one user wants. Ship the sane default or make it per-DocType through Customize Form.
Why: every toggle doubles the test matrix and stays forever.
Exception: when users would legitimately disagree about a visible behaviour, make it configurable per user or per DocType.

### R5. Direction beats local utility
Do not extend surfaces the project is leaving: the website module (Builder replaces it), report-view aggregation (Insights), legacy client JS, `frappe.call` where API v2 is the target. Ask a maintainer when unsure.
Why: every addition to a legacy surface has to be migrated or dropped later.

### R6. Change size matches the problem
A small ask arriving as a large diff is pushed back. If an existing doctype, page, library or API does most of the job, add the missing part there. A "new X" next to an existing X needs a stated limitation of the current one. Half-done PRs are closed, not merged to iterate later.
Why: parallel implementations drift and double the maintenance.

## Root cause

### R7. Fix the root cause where it lives
A fix that makes an error go away without explaining why it happened is rejected. Fix it in the layer that owns it (ORM, util, datatable, shared control), not at one call site. Deleting a guard, condition, style or method to make a symptom disappear is not a fix; the check was protecting something. Read the commit that introduced the behaviour before changing it; odd code is often intentional.
Why: a symptom patch leaves the bug for the next caller.
Exception: a harmless shallow fix may merge under release pressure, with the deep fix noted in the PR.

### R8. Do not add what already exists
Before adding a field, flag, param, endpoint, setting or patch, check whether an existing value, argument, default or `None` already carries the meaning. Make an existing flag tri-state before adding a second one. No patch for things `migrate` already syncs.
Why: two mechanisms for one meaning can disagree, and every new surface is API forever.

```python
# Bad
def get_list(doctype, order_by="modified desc", no_order=False):

# Good: order_by=None means no ordering
def get_list(doctype, order_by="modified desc"):
```

### R9. Reuse before reimplementing
Use `@redis_cache`, `cached_property`, `frappe.generate_hash`, `frappe.db.set_value(update_modified=False)`, `frappe.ui.keys.add_shortcut`, `frappe.ui.freeze`, `frappe.utils.icon`, `str.join` and library defaults before writing new code. One implementation per piece of logic; extract a helper at the second or third repeat.
Why: copies drift, and custom apps copy whatever core does.
Exception: a little duplication beats coupling unrelated modules.

### R10. Smallest correct change, simplest mechanism, no residue
Prefer the one-line fix. Plain functions and `if` blocks; no inheritance towers, monkey-patching, global mutable state, threads or Lua scripts unless proven necessary. Remove unused boot data, unreachable branches, single-use wrappers, params only ever passed one value, properties nothing reads, commented-out code, no-op CSS. Residue is blocking.
Why: complexity and dead code are paid on every read.

### R11. Finish the sweep, keep every surface consistent
A change to one of a parallel set (DocField / Custom Field / Customize Form Field; Link / Dynamic Link; wkhtmltopdf / Chrome; form / grid / list / report / print) is incomplete until the siblings are done. A display or behaviour change applies everywhere the value appears, or not at all.
Why: two surfaces that disagree are a new bug.

### R12. Put the check at the choke point
Validation goes in `validate`, `on_trash` or `on_update`, not in one whitelisted caller.
Why: list view bulk actions, `frappe.client.*`, the REST API and `doc.save()` all skip a check that lives in one endpoint.

```python
# Bad
@frappe.whitelist()
def rename_route(name, route):
    if route_exists(route):
        frappe.throw(_("Route already exists"))

# Good
class WebPage(Document):
    def validate(self):
        self.validate_unique_route()
```

### R13. Do not hardcode what the framework knows
No hardcoded doctype names, `Administrator` checks, naming series, countries, logos, hosts or binary paths. Read hooks, defaults and config. Per-doctype behaviour goes on a DocType or DocField checkbox exposed in Customize Form.
Why: hardcoded values are the branches nobody finds until a site differs.

### R14. Explicit arguments, one return shape
Functions and hooks take named parameters (`doctype`, `name`, `doc`), not dict or kwargs bags. State goes on `doc.flags`, not `frappe.flags`. No sentinel strings. A function returns one shape. Rename on the client, not in the server response.
Why: callers can read a signature; they cannot read a bag.
Exception: hook callbacks may take kwargs so the signature can grow.

### R15. Cover the edge cases, and leave the user a way out
For every new branch ask what happens on `None`, duplicates, the user's own record, a queued job, a submitted document, a deleted doctype, `[Select]`. A new guard must not make the flow that resolves it also throw.
Why: "clearing the field then throws `UpdateAfterSubmitError`; there is no way out."
Exception: no fallbacks for states that cannot happen.

## Backward compatibility

### R16. Break only when not breaking costs more
Established behaviour (select values, ordering defaults, signatures, lifecycle semantics, exception classes, hook timing, export and report columns) is not changed for one use case. List who depends on it across frappe, erpnext, hrms and the other apps. Take the non-breaking variant when there is one. Internal symbols can be dropped; public ones need a compatibility path. Unreleased code owes nothing.
Why: every app on every site pays for a break.
Exception: behaviour that never worked, or hurts most users, may change.

### R17. Deprecate one major before removing
Public functions, paths and params get a `deprecation_warning` in place, one major for apps to migrate, then removal. No proxy classes or inspect-based machinery. Prefer fixing over deleting.
Why: before a major, grep `deprecation_warning` and remove that code. Nothing else to remember.

### R18. Defaults never flip
A new option ships with the old behaviour as default. Experimental capabilities ship opt-in or marked beta. A rejected default may live on as an opt-in setting.
Why: people do not notice a new checkbox. They notice their site changed.

### R19. Add new, migrate, hide old
Never repurpose or retype a field, and never change what `modified` or `creation` mean. Add a new field, migrate on save plus a patch, hide the old one, remove next major. Do not rename or remove CLI flags, kwargs, argument order, module paths or icons apps may use. New arguments go last with a default.
Why: existing rows and calls must survive `bench migrate`.

### R20. Constraint changes ship with a patch
A new unique constraint, validation or default that existing rows would violate blocks `bench migrate`. Ship a patch that repairs the data, or drop the constraint. A patch that needs new schema calls `frappe.reload_doctype` first.
Why: sites with old data cannot update otherwise.

### R21. Breaking changes carry `!` and stay on develop
Use `fix!:` or `feat!:`. Do not backport them. A framework change that needs an ERPNext change lands after the ERPNext PR, with an ERPNext CI run linked. Query builder, permission and core-model changes get that run too.
Why: release notes and the migration guide come from the prefix.

### R22. Do not take features away from regular users
A change that makes a common workflow harder for non-technical users, or quietly disables a feature (data import mapping, URL attachments, saved filters), is reverted. Put the burden on system managers.
Why: users use templates; system managers create them.

## Server side and security

### R23. Business logic lives on the server, completely
A rule enforced in JS (mandatory-depends-on, `set_query` filters, computed values) is also enforced in the controller. Params a check depends on are mandatory. Settings that gate a user are permlevel > 0. Search and validate agree.
Why: the REST API, data import and server scripts never run client code.
Exception: a purely cosmetic client-side permission (hiding a print button) needs no server check.

```python
class Event(Document):
    def validate(self):
        if not self.ends_on:
            frappe.throw(_("End date is required"), title=_("Missing Value"))
```

### R24. Never punch holes in permissions
`ignore_permissions=True`, blanket role grants and permission-less endpoints are not fixes. Use `doc.check_permission()`, `frappe.has_permission` and `frappe.only_for` so Is Owner and User Permissions apply, and give the user the right permission instead. Prefer permlevels over ad-hoc code. Check before `get_doc` or any return, on every branch. Identity comes from `frappe.session.user`, never from the client.
Why: better to give the user the right permission than to create a hole.

```python
# Bad
@frappe.whitelist()
def get_report(user, name):
    return frappe.get_doc("Prepared Report", name, ignore_permissions=True)

# Good
@frappe.whitelist()
def get_report(name):
    doc = frappe.get_doc("Prepared Report", name)
    doc.check_permission("read")
    return doc
```

### R25. Whitelisted endpoints are public URLs
Set `methods=[...]` on security-critical and guest endpoints. Store only hashes of keys and tokens. Never return `site_config` secrets. Website users can call whitelisted methods too. No `allow_guest` on flows that need login.

```python
@frappe.whitelist(allow_guest=True, methods=["POST"])
def subscribe(email):
    ...
```

### R26. Escape at render, never at storage
Do not sanitise on store or globally in a formatter. Escape where the value goes into HTML, per fieldtype. Escape rather than strip. Use `|e` in Jinja.
Why: storing anything is safe; injecting it as HTML is not. Stripping loses data.

```javascript
// Bad
$wrapper.html(`<div>${doc.title}</div>`);

// Good
$wrapper.html(`<div>${frappe.utils.escape_html(doc.title)}</div>`);
```

### R27. A security claim needs a demonstrated bypass
Ask where exactly permissions are bypassed; close if it cannot be shown. Reject rate limits and information hiding that cost more than they protect. Harden once in the shared layer, not per input. But any path that lets a normal user gain admin is blocked whatever the UX cost. Do not widen `safe_exec` or Jinja globals, read files from user input, or allow expressions in `autoname`.
Why: there is no end to designing for stupidity, but privilege escalation beats UX.
Exception: System Manager-authored Jinja and HTML is trusted. Other holes do not justify a new one.

### R28. Fail loudly, catch the specific exception
Permission failures raise `frappe.PermissionError`. No blanket `try/except`, no `log_error` without a traceback, chain with `raise ... from exc`. Promises get `.catch`. Background jobs already log. A friendly catch is scoped to exactly its condition.
Why: failing is better than silently ignoring.

```python
# Bad
try:
    doc.submit()
except Exception:
    pass

# Good
try:
    doc.submit()
except frappe.ValidationError:
    frappe.msgprint(_("Could not submit {0}").format(doc.name))
    raise
```

### R29. Never destroy data silently
No `ELSE NULL` in update queries, no sanitisers that drop content, no defaults that overwrite `creation`, `owner` or `name`. Disable instead of delete. Confirm bulk and destructive actions. Audit tables are immutable.
Why: bad UX beats irrecoverable data loss.

## Performance

### R30. Nothing lands in the hot path for everyone
Anything that runs on every request, document load, save or desk boot is opt-in or free. The common case never pays for the edge case. No API calls or queries on page load; read from `frappe.boot`. Anything added to boot is cached.
Why: per-request overhead multiplies across every site.
Exception: a few bytes in boot beat a separate request.

```javascript
// Bad: one request per form load
frappe.db.get_single_value("System Settings", "float_precision").then(...)

// Good
const precision = frappe.boot.sysdefaults.float_precision;
```

### R31. Think in 100k rows
No `get_doc` in loops or to update one field, no unindexed filters, no full-table sorts, no `limit: 0`, no O(N) Redis scans. Hoist meta lookups and hooks out of loops. Batch link fetches. Cap `IN (...)` near 1000.
Why: users import lakhs of records.

```python
# Bad
for name in names:
    doc = frappe.get_doc("Item", name)
    doc.disabled = 1
    doc.save()

# Good
frappe.db.set_value("Item", {"name": ("in", names)}, "disabled", 1)
```

### R32. Slow or external work goes to a background job
Work over about ten seconds, third-party API calls, bulk PDFs, renames and notification emails are enqueued, never run in a request or `validate`. Heavy work uses `queue="long"`. Jobs are idempotent because hooks run on every retry. Files a job writes on a schedule get a retention window and cleanup. In patches, use an `update` query or `bulk_insert` and commit in batches, never one row at a time.
Why: a worker blocked for a minute is a site down for everyone on that worker.

### R33. Performance changes need numbers
Show profiler output, `EXPLAIN`, benchmarks or bundle deltas at production scale, measured as a real user, not Administrator. A perf change names the cost it removes. No caches that cannot hit, no cache on top of `get_meta` or settings (already cached), no micro-optimisation that adds code for a tiny gain.
Why: a cache is a key, a TTL, invalidation sites and tests, all to skip one indexed query.
Exception: do not optimise paths that run once in a blue moon.

## Database

### R34. Use the highest-level API that does the job
ORM (`frappe.db.get_value`, `set_value`, `get_list`) when it expresses the query; query builder when the ORM cannot; never hand-written dialect SQL. Do not bypass `delete_doc` and controller hooks with `frappe.db.delete` without a stated reason. Let the schema enforce invariants: mandatory fields become `NOT NULL`, a unique constraint beats app-level dedup.
Why: lower-level APIs skip caching, permissions, hooks and portability.

### R35. No `commit()` in document events
Doc-event code never commits; requests commit at the end. Side effects that must survive run `after_commit`. Every state transition calls `check_if_latest`, with no bypass flag.
Why: a commit inside `validate` persists a half-saved document.
Exception: a helper reachable from a GET may commit, and patches commit in batches.

### R36. Parse, don't validate; MariaDB is the reference
Turn known inputs into query builder objects and let it emit SQL. Never regex-check or rewrite generated SQL. When drivers disagree, MariaDB is canonical and Postgres adapts; DB-specific code lives in `frappe/database/<db>/`. Permission filters go in `WHERE`, not `JOIN`. Pass `order_by=None` when order does not matter; tie-break paginated sorts with a unique column. Avoid `ifnull` and `coalesce`, never on `name`.
Why: non-deterministic order makes pagination wrong.

### R37. Pick the right cache and prove invalidation
`@site_cache` is per process and never invalidated; use `@request_cache` for permission-dependent data. Single values use `frappe.cache.get_value`, not a hash. Keys are stable and prefixed. Invalidation covers every mutation; clear and recompute rather than maintain by hand.
Why: a stale permission cache is a security bug.

### R38. Patches only when data moves; DocType JSON only through the UI
No patch for what `migrate` already syncs (doctypes, workspaces, module defs, new-field defaults). DocType JSON is changed through the DocType form or Customize Form and the export committed with its bumped `modified`, child tables included. A hand-edited JSON is sent back. A `modified`-only bump with no field change is reverted. Index changes need a patch or a `modified` bump so `on_doctype_update` runs.
Why: DocType JSON is generated by code; humans and agents should not touch it directly.

## UI

### R39. Design tokens, no CSS duplication, right file
Every colour, weight and spacing is a token or CSS variable; check both themes. Reuse existing classes. Repeated rules go on a parent class. Delete rules with no user. View-specific CSS lives in that view's file. No inline styles, `!important`, `position: fixed` or fixed-height hacks.
Why: more CSS means a larger bundle and more to maintain.
Exception: print CSS stays light; no dark-mode tokens in PDFs.

```scss
// Bad
.sidebar-item { color: #1f272e; font-weight: 420; }

// Good
.sidebar-item { color: var(--text-color); font-weight: var(--weight-medium); }
```

### R40. Espresso components, sprite icons, gray accents
New desk UI uses `es-button` and `es-badge` with data attributes, not bootstrap `btn` and `badge`. Icons come from `frappe.utils.icon()` with names in the sprite; no hand-written SVG, no emoji. Accents are gray, not blue. A new control follows the sibling control; match avatars, indicators, labels, column order and empty states.
Why: keep the design consistent with existing components.

```javascript
// Bad
$(`<button class="btn btn-primary btn-sm"><svg …></svg> Add</button>`)

// Good
$(`<button class="es-button" data-variant="subtle" data-size="sm">${frappe.utils.icon("add", "sm")} ${__("Add")}</button>`)
```

### R41. Defaults serve non-technical users; copy is short
Default filter operator is `=`, not `%`. No "Property Setter" or "DocType" in labels. No icon-only buttons in dialogs. Labels say what happens ("Export all matching rows?", "3 rows updated"). Messages name things the user can find (row number, not a hash). Errors are red; non-fatal messages are warnings. `PermissionError` only for permission problems. Short plain sentences, as brief as the sibling labels.
Why: regular users over power users.

### R42. Bundle size is a budget
The bundle-size check must pass or be justified. New dialogs and panels load on first use via `frappe.require`. Libraries used by a minority stay out of the default bundle. No second frontend framework. No new dependency for trivial things.
Why: bundles grow a few KB at a time until it is 300 KB.

### R43. A dialog beats a new doctype; a permission beats a setting
No doctype for a one-off action or dev-only report; use a button and dialog on the existing doctype, a virtual doctype, or an existing control. Prefer a permission over a setting. A justified setting lives in System Settings with a User-level override that wins. New DocType or DocField properties are exposed in Customize Form.
Why: do not create new UI when you do not need it.

### R44. UX guardrails
Confirm destructive and bulk actions. Secondary actions are not primary buttons. Success toast only when nothing failed; failures name the records. Tab, Enter and Escape keep working. Any control change marks the form dirty. Console stays clean. No forced refresh, no extra scrollbars, no dangerous one-click control next to a frequent action.
Exception: skip the confirm where the label already says it ("Send now").

### R45. Client work is scoped, runs once, cleans up
`this.wrapper.find()`, not global `$()`. No work per row render or animation frame. `.off()` namespaced listeners before `.on()`. Dialogs are singletons. No `setTimeout` or `MutationObserver` when a lifecycle hook exists. No unscoped `localStorage` keys. JS validation must not depend on the awesomplete list, `.grid`, `:visible` or `frm`; think of `set_value`, paste, quick entry and grid rows.
Why: a check per animation frame runs sixty times a second.

```javascript
// Bad
$(document).on("click", ".sidebar-toggle", () => this.toggle());

// Good
this.wrapper.off("click.sidebar").on("click.sidebar", ".sidebar-toggle", () => this.toggle());
```

## Code hygiene

### R46. No comments that say what, no debug noise, no AI attribution
Comments that narrate the code are removed. Issue numbers never go in code. Docstrings that restate the name are dropped; the reasoning goes in the PR. Strip `console.log`, `print`, commented-out code, unused imports, TODOs for another PR. Use `let`/`const`, `??`, `?.`, `.includes()`. Keep methods on the class, not on `frappe.provide` namespaces. `Co-Authored-By: <AI>` and "Generated with …" lines are removed. No `# nosemgrep` in core.
Why: comments rot; two of them are already wrong.
Exception: a non-obvious workaround gets one comment saying why.

### R47. Names say what the thing does
Fieldname mirrors label. Checkbox fieldnames are positive ("Allow X"). No abbreviations or `d`. Plural names return plurals. No `decorators.py` or `functions.py` grab-bags. `snake_case`; `DocType` and `JSON` casing.
Why: it should at least resemble what it does.

### R48. Type discipline
Annotate all params and the return type, or none. Hints must be true (`str | int` for docnames on whitelisted methods; a `Document` cannot cross the API boundary). Lazy imports go behind `if TYPE_CHECKING`. Compare dates with `getdate()`, not strings. `None`, `""` and `0` are different. Compare checkbox and boot values with `cint`, never `=== "1"`. Raise `NotImplementedError` instead of returning a wrong result.

```python
# Bad
if doc.posting_date > today():

# Good
if getdate(doc.posting_date) > getdate():
```

### R49. Translate whole sentences, and only sentences
Wrap the full sentence in `_()` / `__()` with `{0}` placeholders. Never build it from f-strings, `+`, ternaries or template literals. Format after translating. No HTML inside the source string; use `frappe.bold()` or a placeholder. Do not translate `"{0}"`, empty strings, fieldnames, file names, user-authored labels, `df.label` or link values.
Why: constructed strings never get a translation.

```python
# Bad
frappe.throw(_("Cannot delete " + doc.name + " because it is submitted"))

# Good
frappe.throw(_("Cannot delete {0} because it is submitted").format(frappe.bold(doc.name)))
```

### R50. Flat functions, no guards for impossible states
Short functions, early return, `if x := ...:`, `a or default`. Inline a two-line helper used once. No `and`/`or` chaining tricks, nested ternaries, `True if … else False`, redundant casts. `.replace()` and `startswith` over regex. No `getattr`, `hasattr`, `isinstance` or empty-list guards for values that are always set. No `None` defaults on API args that cannot be handled.
Why: guards for impossible states hide real bugs.

### R51. Tests never leak into production code
No `if frappe.in_test`, no `in_import` or `in_patch` escape hatches, no edge case added to make a test pass. `assert` is for invariants and is not blocked by lint.
Why: if you have to do this, you broke something.

## Tests

### R52. New behaviour and bug fixes ship with a test that can fail
Permissions, backups, schema, docstatus transitions, number parsing and anything touching every list view get a test for every promised case. A test that passes without the fix, only checks that nothing raised, swallows the exception, or asserts on generated SQL is rejected. Use `assertQueryCount` for caching claims. Confirm the test fails with the fix reverted.
Exception: a trivial one-liner, a small UI change with a video, or a race the harness cannot reproduce. Say so.

### R53. Test through interfaces, as a real user, with clean fixtures
Assert via public interfaces, not cache internals. Use `new_doctype`, `freeze_time`, `set_request`. Tests set their own preconditions and rely on auto-rollback; no manual commit, no leftover Redis state. A feature that only works as Administrator is a bug: switch user. A permission test that calls `get_all` proves nothing; use `get_list`. Fixtures use `example.com`, never real domains, companies, emails or keys, and stay tiny. No issue numbers in test names.

```python
# Bad
def test_permission(self):
    self.assertTrue(frappe.get_all("Note"))

# Good
def test_permission(self):
    frappe.set_user("test@example.com")
    self.assertFalse(frappe.get_list("Note"))
```

### R54. Flaky tests are fixed, not disabled
The author investigates red CI: run locally, remove the new test to isolate, rebase. A related failure blocks; an unrelated one is named per check and re-run. Never skip a test to get green. If a test expects the old behaviour, update it. UI behaviour changes get a Cypress test when the repro is deterministic.
Why: a disabled test comes back to haunt you.

## PR process

### R55. Develop first, backport later
Fix develop, then `@mergify backport version-N-hotfix` so authorship is kept. A manual port matches the develop diff exactly and carries its dependencies; check the target branch has the prerequisite APIs. Features and behaviour changes wait one to three weeks on develop, or are not backported. A v15 label usually needs v16 too. Breaking changes stay on develop. Retargeting a PR does not work; open a new one.
Why: stable branches are where customers are.
Exception: security and dependency fixes go to stable quickly. A fix that no longer applies on develop may target the hotfix branch. A customer-blocking fix may skip the soak.

### R56. One concern per PR
Unrelated refactors, renames, formatting, `yarn.lock` churn, `.po` hunks and independent bugs go in their own PR so they can be backported and blamed separately. A targeted fix does not touch the surrounding flow. But do not split a six-line change into four PRs, or open a second PR for a tweak to an open one.
Why: unrelated changes in one commit make it hard to find and backport anything.

### R57. User-facing docs live on docs.frappe.io; translations on Crowdin
Hooks, config keys, settings and public utilities land with user-facing docs on docs.frappe.io; internal helpers do not. "Why `no-docs`?" is a fair question. `.po` and `.pot` edits go to Crowdin, never into the repository.

### R58. Revert first, fix later
A merged change that causes support tickets, crashes, performance regressions, bundle-size failures or broken defaults is reverted immediately, before the cause is understood. The revert says why. The author re-raises with the fix.
Why: every hour a regression stays on develop it reaches more sites.

### R59. Stale or unfinished PRs are closed with an open door
Not-ready work goes to Draft; draft means not mergeable. After a nudge, inactive PRs or PRs with too many open issues are closed "for now" with an offer to reopen.

### R60. No automated or AI-generated changesets
A PR generated without manual review, that references code not in the diff, hides the real cause or reimplements an existing component is closed. Suspected AI code needs a video and a plain explanation before further review. No scripted typo sweeps, vendored-library edits or typo-in-comment PRs. Code lifted from an issue, another PR or another app carries the original author (`git commit --author=`); backport the original PR rather than re-author it.
Why: reviewer time is the scarcest resource in the project.
Exception: maintainers may run automated changes themselves after an issue is agreed.

---

## Unsettled

Maintainers disagree on these. State both positions and tag a maintainer.

1. Docstrings: required on every new function, or stripped along with comments.
2. `# nosemgrep`: never in core, or fine with a stated reason.
3. Settings toggles: how strictly R4's exception applies.
4. Explicit `commit()`: never in doc events is agreed; GET-reachable helpers and long patches are not.
5. `get_list` vs `get_all`: where "user-facing" ends and "internal" begins.
6. MariaDB parity vs Postgres strictness for query semantics.
7. Hotfix-branch PRs: always re-raise on develop, or accept when the develop fix no longer applies.
8. Backport soak time: one week, two, three, or "once stable".
9. Docs as a merge gate, or a non-blocking check.
10. Tests for small fixes: always, or manual verification is enough.
11. Duplication vs coupling: no written test for "weird coupling".
12. Admin-authored expressions: Jinja and `visible_if` are trusted, `autoname` expressions were rejected.
13. Deprecation ladder: warn one major and remove the next, or drop internal symbols without warning. "Internal" is not defined.
