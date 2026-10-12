# Threat model: Frappe Framework

## What this project does and where untrusted input enters
Frappe is a full-stack web framework (Python server, JavaScript Desk UI, MariaDB or PostgreSQL, Redis, a Node
Socket.IO server). It runs on the public Internet, often with many sites on one bench and many companies or teams on
one site. Treat every HTTP request as untrusted, from guests and logged-in users alike.

Entry points:
- Every function decorated with `@frappe.whitelist()`, reached through `/api/method/<dotted.path>`, and especially
  those with `allow_guest=True`. Doctype controller methods reached through `run_doc_method`.
- The REST API: `/api/resource/...` and `/api/v2/...` (`frappe/api/`), and the generic list, report and search
  endpoints (`frappe/desk/reportview.py`, `frappe/desk/search.py`, `frappe/model/db_query.py`, the query builder).
  The `fields`, `filters`, `order_by` and `group_by` parameters are user-controlled.
- Website routes (`frappe/www/`), web forms, web views and portal pages (`frappe/website/`).
- Login, password reset, two-factor, OAuth2/OpenID provider, social login, LDAP, API keys, signed URLs and
  impersonation (`frappe/auth.py`, `frappe/twofactor.py`, `frappe/integrations/`, `frappe/www/login.py`).
- File upload, download and private files (`frappe/handler.py`, `frappe/core/doctype/file/`, `frappe/utils/file_manager.py`).
- Templating and sandboxes: Jinja rendering of print formats, email templates, notifications and web pages
  (`frappe/utils/jinja.py`), and `safe_exec`/`safe_eval` behind Server Scripts and condition fields
  (`frappe/utils/safe_exec.py`).
- Realtime rooms (`realtime/`), inbound email (`frappe/email/`), webhooks, data import and export.

## Actors and trust boundaries
From least to most privileged:
1. **Guest**: not logged in.
2. **Website User**: a logged-in portal user. Anyone who signs up on a site with signup enabled is one.
3. **System User**: a Desk user with no special role, or a low-privilege named role.
4. **System Manager**: trusted to configure the site.
5. **Administrator** and anyone with shell access to the bench or write access to `site_config.json`: fully trusted.

The boundaries that matter: one site's data from another site on the same bench; one company's, team's or user's
records from another's on the same site; a role's DocPerm rows; User Permission restrictions; share and assignment;
and the `safe_exec` sandbox, which should hold even against a System Manager.

## Components that matter most
- **Authorization**: whitelisted methods, the REST/list/report API, child tables and linked fields, permission hooks,
  and request arguments that change which permission is checked or turn it off.
- **Injection**: SQL built from request values, including field and ordering names, and misuse of the ORM or query
  builder.
- **Code execution**: `safe_exec`/`safe_eval` escapes, server-side template injection, and shell commands.
- **Authentication and session**: login, password reset, 2FA, OAuth, API keys, signed URLs and impersonation.
- **Files**: path traversal, upload validation and access to private files.

Out of scope: `node_modules/`, vendored third-party JS under `frappe/public/js/lib/`, generated files, test
fixtures, and anything outside this repository (report those to the app they belong to).

## What counts as a finding
A report needs all four:
- **Entry point**: the exact reachable function or route.
- **Actor**: Guest, Website User, plain System User, or a named low-privilege role. Use the least-privileged actor
  that works.
- **Input**: the request-controlled value and how it reaches the sink.
- **Impact**: what the actor reads, writes or executes that they should not.

Report one finding per root cause and list every entry point it reaches. One missing check reached through ten
endpoints is one finding.

## Known non-findings
- Code guarded by `frappe.only_for`, `check_permission`, `has_permission`, or an equivalent check that actually covers
  that actor and that record.
- `ignore_permissions=True` in code reachable only from a scheduled job, patch, install script or test.
- Sinks whose input is a constant or is validated against a hardcoded allow-list.
- Anything only Administrator or System Manager can reach, when the impact does not exceed what that role can
  already do. That includes running code through enabled Server Scripts, System Console or `bench execute`.
  At most, note it as informational.
- Behaviour that only exists because of a weakened development setting: `ignore_csrf`, `developer_mode`,
  `allow_tests`, `server_script_enabled`. If a result depends on any of these,
  say so on the finding, keep only the part that holds without it, and say what must be re-tested.
- Missing security headers that the reverse proxy (nginx) is expected to set, version disclosure, and self-XSS.

## How we rate severity
- **Critical**: a Guest or any logged-in user gets RCE, arbitrary SQL, a full data read, or account takeover.
- **High**: a low-privilege user crosses a trust boundary. They read or write another user's, company's or site's
  data, or escalate their role.
- **Moderate**: partial disclosure, a bypass that needs an unusual precondition, or a control that fails only in one
  configuration.
- **Low**: enumeration, a metadata leak, or missing defence in depth.

## How to exercise it
The image has a bench at `/home/frappe/frappe-bench` with the checkout at `apps/frappe` (`/src` links to it) and a site
named `test_site`. Reproduce findings over HTTP against this site.
- `frappe-services start` starts MariaDB and Redis, which work offline. `frappe-services stop` stops them.
- Web server: `echo '127.0.0.1 test_site' >> /etc/hosts`, then `su frappe -c "cd ~/frappe-bench && bench serve --port 8000" &`
  and `curl http://test_site:8000/api/method/ping`.
- Log in through `/api/method/login` with `{"usr": ..., "pwd": ...}` and reuse the `sid` cookie. Users:
  `Administrator`/`admin`, and with password `scanner-user-pw`: `website@example.com` (Website User),
  `user@example.com` (plain System User, only the `Desk User` role) and `manager@example.com` (System Manager).
- `bench --site test_site console` gives a Python shell on the site, for setting up data a reproduction needs.
- MariaDB root password: `root`.

Desk access is not needed to call an API: unless a method checks for a role, `/api/method/...` works for any
logged-in user, so try `website@example.com` before a desk user, and Guest before either.

Prove the impact without maximising it. Read one record you should not be able to read. Do not destroy data. For a
claim that something is refused, run a positive control as the same user in the same run, showing that a request
that should succeed does succeed. A 403 can come from a check unrelated to the one you are testing.

## Reports and patches
Include the HTTP requests that reproduce the issue on `test_site`, the user they ran as, and a minimal patch against
`develop`.
