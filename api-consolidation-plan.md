# Plan: Public API surface — `@public` contract + endpoint consolidation

Status: proposal (researched 2026-07-18, on `develop`). Not started.
Target release: **v17** — everything here (Phase 0 included) lands on develop
and ships in v17; nothing is backported to v16.

Two workstreams that land together, one per-domain PR at a time:

1. **Contract** — a `@frappe.public` decorator marking endpoints as explicitly
   public, enforcing annotations + docstrings, and attaching machine-readable
   metadata for discovery/OpenAPI.
2. **Structure** — consolidating 525 scattered whitelisted endpoints into
   audience-oriented `api` modules.

They reinforce each other: a move PR is the natural moment to apply `@public`,
add missing annotations/docstrings, and decide whether an endpoint is actually
public at all. The discovery layer then documents the *consolidated* paths,
not the legacy ones.

## Context

The frappe app has 525 production whitelisted endpoints spread across ~170 files
(569 total minus 44 test helpers), of which 56 are guest-accessible. There is no
dominant API module — the surface is smeared across module-level files
(`client.py`, `recorder.py`, `share.py`), `desk/` view helpers, and ~100 doctype
controllers holding 1–12 endpoints each. None of it is marked as public/stable
vs. internal, and annotation/docstring coverage is inconsistent.

Precedents already in the codebase:

- `frappe/core/api/` (`file.py`, `user_invitation.py`) — the consolidation
  pattern to extend.
- `frappe/api/` is **taken** by the REST v1/v2 handlers — a new top-level
  `frappe/api/` namespace is off the table (the `@public` machinery lives in
  `frappe/public_api.py` instead).

### Load-bearing mechanism (verified)

`is_whitelisted` checks function **identity** (membership in the `whitelisted`
set, `frappe/__init__.py:625`), and RPC `cmd` paths resolve via plain attribute
import (`frappe/handler.py:279`). So after moving a function, a one-line
`from frappe.core.api.document import get_list` alias in the old module keeps
every old dotted path working — JS callers, downstream apps'
`override_whitelisted_methods` hooks, stored webhook/shortcut paths. Identity
also means `@public` metadata survives the move and the aliases for free.

### Alias policy (decided)

- **`frappe.client.*`: warn forever, never remove.** These paths are baked
  into every external integration, webhook, and tutorial on the internet. The
  aliases emit deprecation warnings indefinitely but carry no removal date;
  discovery/OpenAPI documents only the new canonical paths.
- **All other aliases:** standard `deprecation_dumpster` staging — warn in
  v17, removable in v18.

---

# Part 1: the `@frappe.public` contract

Only for APIs that are intentionally public: the consolidated `api` modules,
plus controller-file utils that are de-facto public (e.g. assign to). Purely
declarative — `@public` never changes runtime behavior (auth, serialization,
rate limits), so adopting it is always safe.

## API shape

Stacked on top of `@frappe.whitelist` — whitelist = exposure, public =
contract. Errors if the function isn't already whitelisted.

```python
@frappe.public(group="Documents")           # metadata all optional
@frappe.whitelist(methods=["POST"])
def submit(doc: dict) -> dict:
    """Submit a submittable document.

    Runs the full submit lifecycle: validates, fires before_submit /
    on_submit hooks, and sets docstatus to 1.

    :param doc: Document dict, must include doctype and name.
    :return: The submitted document as a dict.
    :raises frappe.PermissionError: If the user lacks submit permission.
    """
```

Works on plain module functions and on `@frappe.whitelist()`-decorated
controller methods.

## Enforcement — two layers

### 1. Import time (dev/CI only; warning in production)

The decorator body checks the cheap structural contract the moment the module
is imported:

- function is already in the `whitelisted` registry
- every parameter (except `self`/`cls`) has a type annotation
- return type is annotated (`-> None` allowed explicitly)
- a non-empty docstring exists

Hard fail when in developer mode or tests; warn in production so a
non-compliant third-party app can't take a prod site down. `inspect.signature`
only — no pydantic adapter construction, no site context (no
`frappe.get_hooks`; decoration happens before site init). Raise a dedicated
exception with a message that says exactly what's missing.

### 2. Linter test (CI only, zero runtime cost)

A framework-provided test that iterates `@public` functions (filtering the
`whitelisted` set for the `__public_api__` attribute) and validates Sphinx
docstring structure:

- standalone imperative summary line, blank line after
- `:param` / `:return:` / `:raises` entries parseable (`docstring_parser`)
- no types in `:param` entries — types come from annotations only

Apps inherit the test via standard test discovery, so violations fail CI
without touching boot or request paths. Param-coverage strictness (every
non-default param must have a `:param` entry) can be tightened here later
without touching the decorator.

## Docstring format

Sphinx style (`:param x:` / `:return:` / `:raises:`) — matches existing
codebase convention.

- First line: standalone imperative summary → OpenAPI `summary`.
- Optional prose body → OpenAPI `description` (behavior, side effects,
  permission implications).
- One `:param` entry per parameter, human meaning only, no types.
- `:return:` when the annotation alone isn't self-explanatory.
- `:raises` entries are the error contract — kept in the docstring (not a
  decorator kwarg) so docs and metadata live in one place; extracted by
  `docstring_parser` for per-status OpenAPI responses.

## Metadata (v1, all optional)

- `group` — logical grouping / OpenAPI tag. The consolidated module map below
  gives the natural group names (`"Documents"`, `"Auth"`, `"Files"`, …).
- `deprecated` — version + replacement string (e.g.
  `"v17: use frappe.client.bulk_update"`). Enables `Deprecation` response
  headers and doc badges later. The consolidation aliases staged through
  `deprecation_dumpster` are the first consumers.

Deferred: `since` (stability version marker), `examples`, decorator-level
`raises`.

## Spec storage: function attribute, no registry

**Decided:** no side-table dict like `whitelisted`. `@public` validates,
attaches the spec directly on the function, and returns the same function
object — it never wraps:

```python
@dataclass(frozen=True)
class PublicAPISpec:
    group: str | None = None
    deprecated: str | None = None

def public(*, group=None, deprecated=None):
    def marker(fn):
        _validate_public_contract(fn)          # dev/CI hard fail, prod warning
        fn.__public_api__ = PublicAPISpec(group=group, deprecated=deprecated)
        return fn                              # same object, not a wrapper
    return marker
```

The spec holds only the *declared* metadata. Everything derivable —
canonical dotted path (`fn.__module__` + `__qualname__`), `methods`
(`allowed_http_methods_for_whitelisted_func`), `allow_guest`
(`guest_methods`), signature, parsed docstring — is computed at read time by
the discovery layer. One source of truth, nothing stored twice, no
registration-order or duplicate-alias concerns.

Discovery enumerates by filtering the existing whitelist registry:

```python
def iter_public_apis():
    for fn in frappe.whitelisted:
        if spec := getattr(fn, "__public_api__", None):
            yield fn, spec
```

**Survival through wrapping.** In practice `@frappe.whitelist` is applied
first and `@public` sits on top, so the attribute lands on the outermost
(dispatched) object and there's nothing to survive. But it's robust to other
orders too: `functools.wraps` copies `__dict__` onto wrappers, so any
later `@wraps`-based decorator carries `__public_api__` along automatically.
A `get_public_spec(fn)` helper additionally walks the `__wrapped__` chain as
a defensive fallback for non-conforming wrappers. The validator likewise sees
through wrapping for free: `inspect.signature` follows `__wrapped__`, and
`wraps` copies `__doc__`.

## Code home

`frappe/public_api.py` — decorator, `PublicAPISpec`, `iter_public_apis()` /
`get_public_spec()` helpers, validators. Re-exported as `frappe.public`.
Keeps `frappe/__init__.py` lean.

---

# Part 2: endpoint consolidation

## Organizing principle

Group by **who calls it**, not where the code lives. Three audiences:
external integrators, the desk UI, and website guests.

An endpoint moves to an `api` module only if it's called from framework-wide UI
or by external clients. Endpoints called only from their own doctype's form JS
stay with the controller (~150 endpoints — `auto_repeat`, `customize_form`,
`email_account` validators, `notification` previews,
`document_naming_settings`, etc.). Of those, the de-facto public ones still get
`@public` in place; the rest stay unmarked and are thereby documented as
internal.

## Target structure

### `frappe/core/api/` — integration/RPC surface (extend existing package)

| File                    | Consolidates                                                                                                                                 | ~Endpoints |
|-------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|------------|
| `document.py`           | `client.py` (21), `model/document.py`, `model/rename_doc.py`, `model/mapper.py`, `share.py`                                                  | 33         |
| `auth.py`               | `handler.py` logout/web_logout, `www/login.py`, `auth.py`, `twofactor.py`, `sessions.clear`, password/signup/impersonate from `user/user.py` | ~18        |
| `user.py`               | remaining `user/user.py` (roles, timezones, theme), `user_invitation` (already here)                                                         | ~15        |
| `file.py` (exists)      | + `handler.py` upload_file/download_file, `file/file.py` optimize, `utils/file_manager.py`                                                   | 13         |
| `permissions.py`        | `core/page/permission_manager` (9), `user_permission` (5), `permission_inspector`, `role` queries                                            | ~17        |
| `workflow.py`           | `model/workflow.py` (5), `workflow/` doctype endpoints (4)                                                                                   | 9          |
| `data_import_export.py` | `data_import` (11), `data_export/exporter`, `utils/csvutils.py`, `modules/utils.export_customizations`                                       | ~14        |
| `background_jobs.py`    | `background_task`, `rq_job`, `submission_queue`, `scheduled_job_type`, `utils/scheduler.py`                                                  | ~11        |
| `diagnostics.py`        | `recorder.py` (7), recorder doctype, `error_log`, `concurrency_limiter`, `system_health_report`, `utils/change_log.py`                       | ~15        |

### `frappe/desk/api/` — desk-UI surface (new package)

| File               | Consolidates                                                                                                                         | ~Endpoints |
|--------------------|--------------------------------------------------------------------------------------------------------------------------------------|------------|
| `form.py`          | `form/load`, `save`, `utils`, `assign_to`, `document_follow`, `linked_with`, `activity`, `like.py`                                   | ~30        |
| `views.py`         | `reportview.py` (10), `listview.py`, `treeview.py`, `calendar.py`, `gantt.py`, `list_filter`, `list_view_settings`, `bulk_update`    | ~25        |
| `kanban.py`        | `kanban_board` (12)                                                                                                                  | 12         |
| `search.py`        | `desk/search.py`, `utils/global_search.py`, `link_preview.py`, tag awesomebar lookup                                                 | ~8         |
| `dashboard.py`     | `dashboard`, `dashboard_chart` (6), `number_card` (6), `dashboard_settings`, `chart_source`, `utils/goal.py`                         | ~17        |
| `workspace.py`     | `desktop.py` (5), `workspace` (7), `workspace_sidebar`, `workspace_customization`, `onboarding.py`, onboarding doctypes, `form_tour` | ~20        |
| `notifications.py` | `desk/notifications.py`, `notification_log`, `notification_settings`, `notification_type`, `push_notification.py`                    | ~15        |
| `report.py`        | `query_report.py` (5), `prepared_report` (6), `report.py`, `auto_email_report`                                                       | ~15        |

**Decided: internal until promoted.** Desk endpoints ship unmarked; individual
ones get `@public` only when there's a deliberate case for a stability promise
(e.g. reportview queries, assign_to). This keeps the freedom to refactor desk
UI internals even though portal builders and mobile apps call these endpoints
today — no promise is implied by the move itself.

### Per-module `api.py`

- `frappe/website/api.py` — the deliberate guest surface: `web_form` (6),
  comments, discussions, `web_page_view`, `www/contact.py`, `help_article`
  feedback, `personal_data_deletion_request`, `email/queue.unsubscribe`.
  Concentrating the 56 guest endpoints (today scattered across 30+ files) into
  one reviewable file is the biggest security-ergonomics win. Every entry here
  gets `@public` applied by hand during the consolidation. **Decided:** no CI
  coupling between `allow_guest` and `@public` — they stay orthogonal; future
  guest endpoints are not forced through the `@public` bar automatically.
- `frappe/printing/api.py` — `utils/print_format.py` (6),
  `print_format_generator`, `www/printview.py`, printing doctype/page helpers (~15).
- `frappe/email/api.py` — `inbox.py` (5), `email/__init__.py`,
  `communication/email.py`, `email_queue` retry/send-now (~12).

### Deliberately left in place

- `integrations/oauth2.py` / `oauth2_logins.py` — coherent protocol-shaped
  files; moving churns the OAuth mental model for no gain.
- Doctype-form-local controller methods (see organizing principle).
- `system_console.execute_code` — leave untouched; whitelisted RCE endpoint
  (System Manager-gated), any move touching it needs its own careful review.
  Never `@public`.
- Everything under `frappe/tests/` (incl. 34 `ui_test_helpers.py` endpoints) —
  not public API.

---

# Rollout

Phase 0 lands the contract machinery; every subsequent per-domain PR does
move + alias + `@public` + docstring/annotation cleanup in one reviewable unit.

1. **Phase 0 — machinery.** Implement `frappe/public_api.py` + `frappe.public`
   re-export. Unit tests for each failure mode (not whitelisted, missing param
   annotation, missing return annotation, missing docstring) and the
   dev/CI-vs-prod gating. Add the Sphinx docstring linter test.
2. **Phase 1 — pilot: `core/api/document.py`.** Move `client.py` +
   `model/document.py` endpoints (highest traffic, cleanest boundaries), leave
   `from <new> import <fn>` aliases at old locations, apply `@public
   (group="Documents")` to every moved endpoint, add the missing
   annotations/docstrings. This stress-tests both the checks and the migration
   mechanics on the canonical public surface.
3. **Phase 2 — guest surface: `website/api.py`.** Consolidate the 56 guest
   endpoints; all get `@public`. Biggest security-review payoff.
4. **Phase 3 — remaining domains.** One PR per row of the tables above, in
   whatever order contributors pick them up. Update in-repo JS callers
   (`frappe.call({method: ...})`) in the same PR; aliases are for downstream
   apps and stored data.
5. **Phase 4 — deprecation + consumers.** Stage alias warnings through
   `deprecation_dumpster` per the alias policy above (warn in v17, removable
   in v18 — except `frappe.client.*`, which warns forever and is never
   removed), marking staged aliases via `@public(deprecated=...)` where
   applicable. Ship the discovery endpoint
   (`/api/method/frappe.discovery.get_public_apis`) and/or OpenAPI plugin
   consuming `iter_public_apis()`.

## Raw inventory

Full AST-extracted endpoint list (file, line, func, decorator opts) was saved
during research; regenerate with:

```sh
grep -rn "@frappe.whitelist" --include="*.py" frappe/
```

or the AST script: walk `frappe/`, parse each `.py`, collect functions whose
decorator name contains `whitelist`, recording `allow_guest` / `methods` /
`xss_safe` kwargs.
