# Dropping email as User primary key ([#26189](https://github.com/frappe/frappe/issues/26189))

Context: `User.name` is the email address today. Emails change, people get renamed across
domains, and every rename is a full-database rewrite. The plan: make `name` a stable opaque
ID (naming series `USER-.#####`) for **new** users, grandfather existing users as-is, and
demote `email` to a regular editable field so changing it no longer requires a rename.

**What this buys us — and what it does not.** It makes the *referential* identity stable:
link fields, `owner`/`modified_by`, and `frappe.session.user` stop churning when someone's
email changes. It does **not** make the login credential stable — login moves from a
mutable `name` to a mutable `email`. That's the correct goal, but nobody should expect a
"stable login id." It also makes provider-uid mapping (LDAP/social) the only stable join
key we have, not a nice-to-have (D9).

All open decisions are resolved — see "Decisions" at the end for each choice and its
rationale. Everything below is verified against `develop` (frappe +
erpnext/hrms/crm/lms as a downstream sample) and a live site's schema/data.

---

## How the coupling works today

The name↔email identity is enforced in exactly three places in `user.py`:

1. `autoname()` (`user.py:195-201`) — `self.name = self.email.strip().lower()`.
   Administrator/Guest bypass this via transient `is_admin`/`is_guest` flags and get
   `name = first_name`.
2. `validate()` (`user.py:225-227`) — the reverse lock: for non-standard users,
   `self.email = self.name` on **every save**. Email is not actually editable today; the
   field is decorative.
3. `after_rename()` (`user.py:708`) — `set_value("User", new_name, "email", new_name)`.

So Administrator and Guest are *already* decoupled (`name != email`, they carry
`admin@example.com` / `guest@example.com` from `install.py:76-100`). The framework already
tolerates two users whose name is not an email — that's the existence proof that this can
work, and why grandfathered email-names are safe to keep forever.

## Is the email field sound? No.

- **No unique constraint, no index.** `user.json` declares `email` as `reqd` only —
  no `unique`, no `search_index`, no `set_only_once`. Verified on a live site:
  `SHOW INDEX FROM tabUser` has unique keys on `username`, `mobile_no`, `api_key` — and
  nothing at all on `email`. Uniqueness today is purely a side effect of `name == email`
  and the PK. Decouple them and you have **zero** enforcement.
- **Real data already diverges.** On my dev site: 5 of 137 users have `name != email`,
  including one duplicate email across two users. Standard users diverge by design; the
  rest are drift from historical renames.
- **Case / collation (D6).** `autoname` lowercases, but `db_set`/data-import/raw-SQL writes
  don't, and `validate` doesn't run on those paths. We enforce with `unique: 1` +
  strip/lowercase in `validate`. On MariaDB `utf8mb4_unicode_ci` makes the index
  case-insensitive, so this holds for the DB the vast majority of sites run. **Known
  limitation:** on Postgres a case-variant duplicate can still slip in via those bypass
  paths. Accepted as a documented gap; a functional `LOWER(email)` index would close it but
  is out of scope for v1.

**Email-hardening patch (ship first — see rollout).** A `bench migrate` patch on `tabUser`
that: (1) backfills `email = name` for divergent non-standard users — `name` is the
authoritative login id today, so this preserves login; **report every overwrite** since a
newer address in `email` is destroyed; (2) dedupes, **bailing loudly** if duplicates remain;
(3) adds `unique: 1`, strip+lowercase normalization, and `search_index` on `email`. No
downtime, no session invalidation — no `name` value changes.

## What breaks

### Framework: naming & save path
The three coupling sites above all change: `autoname` gains the series for new users;
`validate`'s `self.email = self.name` is deleted (email becomes its own source of truth);
`after_rename` and `validate_rename` (`user.py:684`) are deleted with rename (D4). Deleting
the whole-database `owner`/`modified_by` crawl in `after_rename` is the point — that class
of pain evaporates.

### Login & credentials
- `User.find_by_credentials` (`user.py:860`) — docstring says "find user by email" but the
  filter is `{"name": user_name}`. Must become `{"email": ...}` (+ username/mobile per
  settings). **The** login fix. Safe to ship in the prep minor (while `name == email` it
  matches the same rows), but pin it *after* the email-hardening patch.
- `__Auth` keys on `(doctype, name, fieldname)` and API-key auth (`auth.py:734-760`) keys on
  the `api_key` field — both survive, and since names never change post-creation, nothing
  migrates.
- `reset_password(user)` (`user.py:1184`) receives an **email** from the forgot-password
  form and does `get_doc("User", user)` — needs email→name resolution.
- Email-link login (`www/login.py:171,187`) — `exists("User", {"name": email})` and
  `login_as(email)`. Both break for series-named users.
- **`user_id` cookie** (`auth.py:220-223`) carries `User.name`; `frappe.session.user`
  becomes an opaque ID for new users. Integrations reading it as an email break. This is the
  semantic change to document loudest (D8: keep the cookie as-is).

### 2FA
OTP secrets live in `__2fa` defaults keyed `f"{user}_otpsecret"`, and the Fernet key embeds
the user name (`f"{user}.otpsecret"`, `twofactor.py:133-142`). This was a hazard **only
under mass rename** — which we never do. Names are stable by construction, so 2FA storage
keyed on `name` needs no action. Noted so nobody reintroduces a rename path without
remembering it couples here.

### Social login / LDAP / invitations — `get_doc("User", email)` sites
All treat an email string as the docname and need the resolution helper instead:
`utils/oauth.py:219,239,263` (social login match + `login_as(email)`),
`ldap_settings.py:213-214,377` (LDAP sync; its `update_user_fields` already refuses to touch
`email` — that restriction lifts), `core/api/user_invitation.py:160`,
`user_invitation.py:100`, `personal_data_deletion_request.py:86`,
`personal_data_download_request.py:34`, `setup_wizard.py:311`, `commands/site.py:721`,
`www/qrcode.py:36-38`, `communication.py:359`. Sites that already do it right (filter on the
field): `sign_up` (`user.py:1128`), `contact.py:84`, `lms/user.py:31`.

### Email sending — the biggest behavioral cluster
`frappe.sendmail` does **no** user→email resolution; recipients are `split_emails()` and
used verbatim (`email_queue.py:660-666`). Call sites passing user names work today only
because name == email; afterward they mail `USER-00042@nowhere` — no error, silent delivery
failure.

`get_formatted_email` is **not** an offender: it calls `get_email_address(user)` =
`frappe.db.get_value("User", user, "email")` (`utils/__init__.py:81-86`), which already
resolves name→email and keeps working for series names. The real offenders build recipients
from `.name`/`.owner` and never touch the email field:
- `get_system_managers()` (`utils/user.py:315-344`) — `formataddr((full_name, p.name))`.
  **The load-bearing fix.** Consumed in `backups.py:484`, `user.py:1337`,
  `email/__init__.py:15`, `auto_repeat.py:479` (also appends `self.owner` raw).
- `document_follow.py:119-166` — sends to `DocumentFollow.user` names directly.
- `notification.py:642,887-895` — assignees (`ToDo.allocated_to`) appended to recipients.
- `communication/mixins.py:18-37` — `doc.owner` as recipient fallback.
- `enqueue_create_notification` (`notification_log.py:126-191`) expects **emails** but
  `assign_to.py:314`, `share.py:289`, `email_account.py:671-679` feed it **names** → zero
  notifications, silently. The API should take names and resolve emails itself.

### Client-side / JS
- `footer.js:63` — `comment_email: frappe.session.user`.
- `user_settings_dialog.js:185` — falls back to session user as email.
- `templates/emails/new_user.html:6` — "Your login id is: {{ user }}" renders the name;
  must render email/username.
- Most timeline/inbox JS already uses `frappe.session.user_email` (from `boot.user.email`,
  `desk.js:337`) — the pattern to standardize on.

### UX: Link fields and lists
Link fields render raw `name` — readable for grandfathered users, a meaningless serial for
new ones. `user.json` has `title_field: full_name` but not `show_title_field_in_link`, and
`search_fields` is only `full_name`. Set `show_title_field_in_link: 1` and `search_fields:
full_name,email,username`. Mandatory polish.

### Downstream apps (sampled: erpnext, hrms, crm, lms)
Link-to-User field counts (frappe 41, erpnext 35, hrms 15, crm 14, lms 27) all survive —
they're links; grandfathered values stay valid, new values are just series ids. The breakage
is where a user name meets an email field:

- **erpnext**: `request_for_quotation.py:226,243` (`get_doc("User", email)` **and**
  `contact.email_id = user.name`), `portal/utils.py:81-90` (portal Contact with
  `email_id = session.user`), `payment_request.py:492` (`payer_email` falls back to session
  user), ~13 `get_users_with_role(...) → sendmail(recipients=...)` sites.
- **hrms**: `utils/__init__.py:53-59` (`get_employee_email` returns `user_id` as an email),
  `employee_reminders.py:108,231` (birthday mails to `user_id`),
  `leave_application.py:736-739` (`or contact` fallback).
- **crm**: `crm_invitation.py:99` (`get_doc("User", email)`), `api/event.py:308` (owner as
  sendmail recipient), frontend `stores/users.js:24-45` — store keyed by name, `getUser(email)`
  called from ~84 sites, with a comment acknowledging the name==email assumption.
- **lms**: `utils.py:127` (`get_doc("User", email)`), `lms_course.py:132` (user name to
  sendmail), `payments.py:77,166` (payer email / address lookup by session user).

**Blast radius:** link-field comparisons (`field == frappe.session.user`) — the vast
majority of `session.user` uses — survive untouched. The breakage is a long tail of
email-conflation that **mostly fails silently** (undelivered mail, missed notifications,
unmatched contacts). That's the argument for the narrow sendmail shim + deprecation warnings
(D3) over a hard cut.

---

## Work required

1. **Email hardening** (prep minor, first): the patch above + `unique`/`search_index`/
   normalization on the field.
2. **Login**: `find_by_credentials` → `email` filter, pinned after (1).
3. **Resolution helper**: one canonical `frappe.get_user_by_email(email)` and convert every
   `get_doc("User", <email>)` site listed above.
4. **Mail**: fix `get_system_managers`; make `enqueue_create_notification` accept names;
   audit `document_follow`/`notification.py`/`communication/mixins.py`; add the narrow
   `sendmail` shim (D3).
5. **Naming**: series `USER-.#####` for new regular users; Administrator/Guest stay literal;
   existing users untouched.
6. **Save path**: delete `validate`'s `email = name`; email editable by System Manager only
   in v1 (D5).
7. **Rename**: `allow_rename: 0`; delete `after_rename` crawl + `validate_rename` (D4).
8. **UX / templates / JS**: link-title fields; `new_user.html` login id → email; audit
   `session.user`-as-email JS.
9. **LDAP/social** (D9): store a provider-uid → user mapping (OAuth already has `sub` via
   User Social Login; LDAP needs one on username/DN), email as fallback-with-warning.

## Rollout

1. **Prep minor (non-breaking, safe while `name == email` holds):** work items 1–4 above.
   - **Deprecation-warning caveat:** while `name == email`, a name used as an email is
     byte-identical to a real one — no clean predicate to warn on without firing on every
     legitimate call. So name-as-email deprecation warnings are **deferred to the major** (or
     gated on the narrow predicate "matches a `User.name` AND that user's `email` differs",
     at a query per recipient). Don't promise blanket warnings in the prep minor.
2. **Major release:** work items 5–9 — series naming, `validate` decoupling, rename
   disabled, LDAP/social mapping, link-title UX, `new_user.html` fix, and docs for the
   `session.user` semantic change and the shim's deprecation timeline.

Existing sites need no name migration: users are grandfathered, sessions stay valid, and
nothing that stored a Frappe user id externally breaks — because no `User.name` changes.

## Decisions

- **D1 — naming scheme: fixed series `USER-.#####`.** Username-as-name recreates the rename
  problem the moment someone wants a new handle; configurability invites per-site divergence
  downstream code must then tolerate. `username` already exists as the human handle — keep
  identity and vanity separate.
- **D2 — grandfather (Strategy A), no mass rename, ever.** All mass-rename machinery (the
  `_assign`/`_liked_by` JSON crawl, `DefaultValue.parent`, `__UserSettings.user`, orphaned
  Dashboard Settings, 2FA re-encryption) is explicitly out of scope and removed from this
  plan. Existing email-names persist forever as valid PKs, exactly like Administrator/Guest.
- **D3 — narrow sendmail shim, deprecated, killed in two majors.** Resolve only recipient
  strings with no `@` that exactly match a `User.name` → that user's email; warn. Clean under
  grandfathering: existing email-names contain `@` (shim never fires, verbatim works because
  name==email); new series names have no `@` (shim resolves them). Cost: one query per
  unresolved recipient.
- **D4 — rename disabled.** Stable ids that can be renamed aren't stable, and the
  whole-database crawl is the code we're deleting. Email changes are now a field edit.
- **D5 — email editing admin-only in v1.** System Manager edits the field; because `validate`
  no longer forces `email = name`, this works for grandfathered users too (name stays as the
  old email, cosmetically). Self-service is a later step gated on current-password or
  verification-link confirmation — email is a login + reset channel, so unverified self-edit
  is an account-takeover primitive (XSS/CSRF → change email → reset password).
- **D6 — unique across disabled users too** (re-enabling must not create ambiguity; login
  filters enabled anyway); **code normalization only** — holds on MariaDB via ci-collation,
  with the documented Postgres bypass gap above.
- **D7 — keep `email` `reqd: 1` for now.** Making it optional for API-key-only bot/service
  users is a separate discussion — half the mail paths assume it exists.
- **D8 — keep the `user_id` cookie as-is** (now opaque for new users). It was always
  documented as the user id; add nothing.
- **D9 — provider-uid mapping for LDAP/social.** With mutable emails, email-match silently
  forks a duplicate user when the provider-side email changes. Now load-bearing, not
  optional: provider-uid is the only stable join key once email is mutable.

## Research basis

- frappe `develop` at `aa56ab185b`, apps sampled: erpnext, hrms, crm, lms.
- Live-site checks (`SHOW INDEX FROM tabUser`, name/email divergence counts).
- Key files: `frappe/core/doctype/user/user.py`, `frappe/auth.py`,
  `frappe/utils/password.py`, `frappe/utils/__init__.py`, `frappe/utils/user.py`,
  `frappe/twofactor.py`, `frappe/utils/oauth.py`,
  `frappe/email/doctype/email_queue/email_queue.py`,
  `frappe/desk/doctype/notification_log/notification_log.py`.
