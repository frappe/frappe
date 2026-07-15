# Dropping email as User primary key ([#26189](https://github.com/frappe/frappe/issues/26189))

Context: `User.name` is the email address today. Emails change, people get renamed across
domains, and every rename is a full-database rewrite. The plan is to make `name` a stable
opaque ID (naming series like `USER-.#####`, possibly configurable) and demote `email` to
a regular mutable field. This document is the research: what's coupled, what breaks, what
the migration must do, and the decisions we need to make before writing code.

Everything below is verified against `develop` (frappe + erpnext/hrms/crm/lms as a
downstream sample) and a live site's schema/data.

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
work.

## Is the email field sound? No.

- **No unique constraint, no index.** `user.json` declares `email` as `reqd` only —
  no `unique`, no `search_index`, no `set_only_once`. Verified on a live site:
  `SHOW INDEX FROM tabUser` has unique keys on `username`, `mobile_no`, `api_key` — and
  nothing at all on `email`. Uniqueness today is purely a side effect of `name == email`
  and the PK. Decouple them and you have **zero** enforcement.
- **Real data already diverges.** On my dev site: 5 of 137 users have `name != email`,
  including one duplicate email across two users. Standard users diverge by design;
  the rest are drift. Any site that's been through user renames can have stale emails.
- **Case sensitivity**: `autoname` lowercases, but a direct `db_set`/data-import write to
  `email` won't. The unique index needs a defined collation story (utf8mb4_unicode_ci is
  case-insensitive on MariaDB, Postgres is not — needs `LOWER()` normalization in code,
  not just the index).

**Required regardless of the naming change:**

1. Patch: backfill `email = name` for non-standard users where they diverged (name is the
   authoritative login identity today; the email field is the stale one).
2. Patch: dedupe — after backfill, duplicates should be impossible for non-standard users,
   but the patch must verify and bail loudly if not.
3. Add `unique: 1` + normalization (strip + lowercase) on `email` in code, mirroring what
   `autoname` does today.

## What breaks

### Framework: naming & save path
- `autoname`/`validate`/`after_rename` (above) — all three must be replaced. `validate`'s
  `self.email = self.name` inverts: email becomes the source of truth for the email field,
  full stop.
- `validate_rename` (`user.py:684`) validates the *new name* as an email — dies under a
  series. IMO rename should be disabled entirely once names are stable (the issue proposes
  this); `after_rename`'s all-tables `owner`/`modified_by` rewrite exists *only* to service
  email changes, and that entire class of pain evaporates.

### Login & credentials
- `User.find_by_credentials` (`user.py:860`) — the docstring says "find user by email" but
  the filter is `{"name": user_name}`. Must become `{"email": ...}` (plus existing
  username/mobile options). This is **the** login fix; everything funnels through it.
- `__Auth` is keyed `(doctype, name, fieldname)` — correct design, keys on `name`. Once
  names are stable, passwords stop moving on email change (today `rename_password`
  moves them). No change needed post-migration, but the migration must rewrite
  `__Auth.name` for every renamed user.
- API key auth (`auth.py:734-760`) keys on the `api_key` field → survives unchanged.
- Password-reset links key on `reset_password_key` hash → survive. But the public
  `reset_password(user)` endpoint (`user.py:1184`) receives an **email** from the forgot-
  password form and does `get_doc("User", user)` — needs email→name resolution.
- Email-link login (`www/login.py:171,187`) — `exists("User", {"name": email})` and
  `login_as(email)`. Both break.
- **`user_id` cookie** (`auth.py:220-223`) carries `User.name`. Client code (ours and
  anyone's integration) that reads it as an email breaks. `frappe.session.user` becomes an
  opaque ID everywhere — that's the semantic change to document loudest.

### 2FA — silent data loss hazard
OTP secrets live in defaults keyed `f"{user}_otpsecret"` under parent `__2fa`, and —
the footgun — the **Fernet encryption key embeds the user name**: `f"{user}.otpsecret"`
(`twofactor.py:133-142`). Rename a user without re-encrypting and their 2FA secret is
unrecoverable ciphertext; they're locked out. The migration must decrypt-with-old-name →
re-encrypt-with-new-name, not just rename the key. Same treatment for `{user}_otplogin`
defaults and the QR-code File rows (`attached_to_name = user`).

### Social login / LDAP / invitations — `get_doc("User", email)` sites
All of these treat an email string as the docname and need a `resolve by email field`
helper instead:

- `utils/oauth.py:219,239,263` — social login matches returning users by
  `get_doc("User", email)` and calls `login_as(email)`.
- `ldap_settings.py:213-214,377` — `exists/get_doc("User", email)` during LDAP sync.
  (LDAP's `update_user_fields` already refuses to update `email` — that restriction lifts.)
- `core/api/user_invitation.py:160`, `user_invitation.py:100`,
  `personal_data_deletion_request.py:86`, `personal_data_download_request.py:34`,
  `setup_wizard.py:311`, `commands/site.py:721`, `www/qrcode.py:36-38`,
  `communication.py:359` (`get_value("User", self.sender, ...)` where sender is an email).
- Counter-examples that already do it right (filter on the field): `sign_up`
  (`user.py:1128`), `contact.py:84`, `lms/user.py:31`.

### Email sending — the biggest behavioral cluster
Verified: `frappe.sendmail` does **no** user→email resolution. Recipients are
`split_emails()` and used verbatim (`email_queue.py:660-666`). Every call site that passes
user names as recipients works today only because name == email. After the change those
mails go to `USER-00042@nowhere` — no error at enqueue time, just silent delivery failure.

Core offenders:
- `get_formatted_email(user)` (`utils/__init__.py:100`) — falls back to
  `validate_email_address(user)`, i.e. "the name is the email". This is the load-bearing
  helper; fixing it fixes many callers, and its fallback must become "resolve name →
  email field".
- `get_system_managers()` (`utils/user.py:315-344`) — builds `formataddr((full_name,
  p.name))` from the *name*; consumed as recipients in `backups.py:484`, `user.py:1337`,
  `email/__init__.py:15`, `auto_repeat.py:479` (which also appends `self.owner` raw).
- `document_follow.py:119-166` — sends to `DocumentFollow.user` names directly.
- `notification.py:642,887-895` — assignees (`ToDo.allocated_to`) appended to recipients.
- `communication/mixins.py:18-37` — `doc.owner` as recipient fallback.
- `enqueue_create_notification` (`notification_log.py:126-191`) expects **emails** (it
  resolves `{"email": ("in", ...)}` → names), but `assign_to.py:314`, `share.py:289`, and
  `email_account.py:671-679` feed it **names**. Post-change these produce zero
  notifications, silently. The API should take names and resolve emails itself.

### Client-side / JS
- `footer.js:63` — `comment_email: frappe.session.user`.
- `user_settings_dialog.js:185` — falls back to session user as email.
- `templates/emails/new_user.html:6` — "Your login id is: {{ user }}" renders the name;
  must render email/username instead.
- Most timeline/inbox JS already uses `frappe.session.user_email` (set from
  `boot.user.email`, `desk.js:337`) — the pattern to standardize on.

### UX: Link fields and lists
User link fields render the raw `name` today — i.e. the email, which is readable.
`user.json` has `title_field: full_name` but `show_title_field_in_link` is **not** set and
`search_fields` is only `full_name`. With `USER-.#####` names, every user link in every
app shows a meaningless serial unless we set `show_title_field_in_link: 1` and add
`email` to `search_fields`. This is mandatory polish, not optional.

### Downstream apps (sampled: erpnext, hrms, crm, lms)
Link-to-User field counts: frappe 41, erpnext 35, hrms 15, crm 14, lms 27 — these all
survive (link values migrate with the rename). The breakage is where a user name meets an
email field:

- **erpnext**: `request_for_quotation.py:226,243` (`get_doc("User", email)` **and**
  `contact.email_id = user.name`), `portal/utils.py:81-90` (portal Contact created with
  `email_id = session.user`), `payment_request.py:492` (`payer_email` falls back to
  session user), ~13 `get_users_with_role(...) → sendmail(recipients=...)` sites.
- **hrms**: `utils/__init__.py:53-59` (`get_employee_email` returns `user_id` as an
  email), `employee_reminders.py:108,231` (birthday mails to `user_id`),
  `leave_application.py:736-739` (`or contact` fallback).
- **crm**: `crm_invitation.py:99` (`get_doc("User", email)`), `api/event.py:308`
  (owner as sendmail recipient), and the frontend `stores/users.js:24-45` — the user
  store is keyed by name and `getUser(email)` is called from ~84 sites. The store even has
  a comment acknowledging the name==email assumption.
- **lms**: `utils.py:127` (`get_doc("User", email)`), `lms_course.py:132` (user name to
  sendmail), `payments.py:77,166` (payer email / address lookup by session user).

Blast radius conclusion: link-field comparisons (`field == frappe.session.user`) — the
overwhelming majority of `session.user` uses — survive untouched. The breakage is a
long tail of email-conflation, and **most of it fails silently** (undelivered mail,
missed notifications, unmatched contacts). That's the argument for compatibility shims +
deprecation warnings rather than a hard cut.

---

## Framework changes required (new behavior)

1. **Naming**: `autoname` → naming series (`USER-.#####`) for regular users; keep
   `Administrator`/`Guest` literal. Decide configurability (D1 below).
2. **Email hardening**: `unique: 1`, strip+lowercase normalization in `validate`,
   `search_index`, and the backfill/dedupe patch — shippable independently, before the
   naming change. Do this first.
3. **Login**: `find_by_credentials` matches on `email` (+ username/mobile per settings).
4. **Resolution helper**: one canonical `frappe.get_user_by_email(email)` (or
   `User.get_by_email`) and convert every `get_doc("User", <email>)` site listed above.
5. **Mail resolution**: fix `get_formatted_email` + `get_system_managers` to read the
   `email` field; make `enqueue_create_notification` accept names. Decide whether
   `sendmail` itself grows a user-name→email resolution shim (D3).
6. **Rename**: disable user rename (`allow_rename: 0`), delete `after_rename`'s
   owner/modified_by crawl. Renaming is the *problem* this change deletes.
7. **UX**: `show_title_field_in_link: 1`, `search_fields: full_name,email,username`.
8. **Templates/JS**: `new_user.html` login id → email; audit `session.user`-as-email JS.
9. **2FA**: key OTP storage/encryption on `name` going forward (it already does — it's the
   migration that must re-encrypt).

## Migration for existing sites

Two viable strategies:

### Strategy A — grandfather existing users
Only new users get series names; existing users keep email-names forever (they're valid
primary keys, just ugly history — exactly like Administrator/Guest today).

- Pros: zero-risk, zero-downtime, no mass rewrite. All the *code* fixes above are still
  required (they're correctness fixes independent of naming), and once they're in, mixed
  naming just works.
- Cons: two naming regimes forever; the "email changed" pain persists for grandfathered
  users (their name still leaks the old email — cosmetic, since email field is now the
  functional one and *is* mutable); sites can never assume names are opaque.

### Strategy B — mass-rename all existing users
One patch renames every user row to its new series name. This is what `rename_doc` +
`User.after_rename` do per-user today, but naively looping them is O(users × (40+ link
fields + all tables × 2 for owner/modified_by + dynamic links)) individual UPDATEs — on a
site with 10k users and millions of rows this is hours of full-table scans. There is no
set-based bulk rename precedent in core patches (all historical "rename" patches are
DocType renames, not mass row renames). The patch must be hand-rolled, per-table,
set-based (build an old→new map table, then one `UPDATE ... JOIN` per column):

Covered by existing machinery (must be reimplemented set-based):
- `tabUser.name` + child table `parent` (Has Role, User Email, Block Module, User Social
  Login, User Role Profile, ...)
- Every Link-to-User column: 41 in frappe + per-app (35/15/14/27 in
  erpnext/hrms/crm/lms) + Custom Fields with `options: User` + Property Setters —
  enumerable at runtime via `get_link_fields("User")`
- Dynamic links (ToDo reference, User Permission `for_value`, Comment, DocShare, Tag Link,
  Event participants, ...) via `get_dynamic_link_map()`
- `owner` / `modified_by` on **every** table
- `__Auth.name`, `tabFile.attached_to_name`, `tabVersion.docname`
- Notification Settings PK (name == user)

**Not covered by any existing machinery** (the misses, confirmed in `rename_doc.py`):
- `_assign` and `_liked_by` JSON arrays on every table that has them (rename only touches
  `_assign` on merge, and only on the renamed doc itself)
- `tabDefaultValue.parent` (user-scoped defaults, incl. `__2fa` rows)
- `__UserSettings.user` column (only the `data` filter values get rewritten)
- Dashboard Settings PK (name == user; rename updates its `user` link field but not the
  record name → orphaned settings)
- 2FA secrets: decrypt/re-encrypt (Fernet key embeds the name — see above)
- `__global_search` (rebuild), Version/Comment *content* (old names in historical JSON —
  IMO leave as-is, it's history)
- Plain Data fields anywhere that hold a user name (unenumerable; third-party apps only)

Additional Strategy B costs:
- **All sessions invalidated** (`Sessions.user` + `user_id` cookies) — every user logs in
  again. Acceptable for a major release.
- **External systems break**: anything that stored Frappe user IDs outside the database
  (webhook consumers, `X-Site-User` header consumers (`frappecloud_billing.py:38`), OAuth
  integrations that mapped on user id rather than the `sub` claim, exported reports).
  Unfixable by us; release-notes material. (OAuth `sub` is already the User Social Login
  userid, not the name — that was a good call, it survives.)
- Site-size-dependent downtime; needs a maintenance-mode patch with per-table progress.

**IMO: A-then-optional-B.** Ship the decoupling + email hardening + shims with
grandfathered names (Strategy A) — that alone delivers the actual feature ("email is
mutable, identity is stable"), because a grandfathered user's *name* no longer has to
track their email. Ship the mass rename as a separate opt-in `bench` command
(`bench rename-users`) for sites that want uniform naming, rather than forcing hours of
migration on every site at `bench migrate` time. The rename tooling has to exist anyway
for Frappe Cloud, but coupling it to the upgrade punishes everyone for cosmetics.

## Rollout order

1. **v-next minor (prep, non-breaking)**: email backfill + dedupe patch, `unique` on
   email, `find_by_credentials` → email filter, resolution helper + convert core
   `get_doc("User", email)` sites, mail-path fixes (`get_formatted_email`,
   `get_system_managers`, `enqueue_create_notification`), deprecation warnings on
   name-as-email fallbacks. All safe while name == email still holds.
2. **Major release**: series `autoname` for new users, `validate` decoupling (email
   becomes editable), rename disabled, link-title UX, docs for the `session.user` semantic
   change.
3. **Separate tooling**: opt-in bulk rename command implementing the Strategy B table
   above, plus the 2FA re-encryption.

## Open decisions

- **D1 — naming scheme.** `USER-.#####` series vs configurable (naming rule on User) vs
  username-as-name (issue #26189 actually suggests user-chosen ids like `ankush`).
  IMO: fixed series. Username-as-name recreates the rename problem the moment someone
  wants a different handle; configurability invites per-site divergence that downstream
  code then has to tolerate anyway. `username` already exists as the human-friendly
  unique handle — keep identity and vanity separate.
- **D2 — migrate existing users or grandfather?** (Strategy A vs B vs A+opt-in-B above.
  My take: A + opt-in B.)
- **D3 — sendmail compatibility shim.** Should `sendmail`/email-queue resolve recipient
  strings that match a User name (or contain no `@`) to that user's email? Pro: absorbs
  the entire long tail of core + third-party call sites passing names, converts silent
  delivery failure into working mail. Con: magic, an extra query per recipient, and
  ambiguity is real once emails and names are distinct namespaces. IMO: yes, but narrow —
  resolve only strings with no `@` that exactly match a User name, and emit a deprecation
  warning. Kill it two majors later.
- **D4 — rename: disable or keep?** IMO disable. Stable ids that can be renamed aren't
  stable, and `after_rename`'s whole-database crawl is the code we're trying to delete.
- **D5 — email mutability rules.** Freely editable by the user, or admin-only /
  verification-required? Email is a login credential and password-reset channel; letting
  a session change its own email unverified is an account-takeover primitive
  (XSS/CSRF → change email → reset password). IMO: require current-password or
  verification-link confirmation, like every serious auth system.
- **D6 — uniqueness scope & collation.** Unique across disabled users too? (IMO yes —
  re-enabling must not create ambiguity, and `find_by_credentials` filters enabled at
  login anyway.) Case-insensitivity on Postgres needs explicit lowercase normalization.
- **D7 — `email` reqd?** It's `reqd: 1` today. Bot/service users
  (API-key-only) have no real inbox and currently get fake emails. Once name isn't email,
  we *could* make email optional for non-login users. IMO: keep reqd for now, separate
  discussion — half the mail paths assume it exists.
- **D8 — `user_id` cookie.** Keep the name (now opaque) or rename/add an email cookie for
  compat? IMO: keep as-is, it was always documented as the user id; add nothing.
- **D9 — LDAP/social matching key.** Both currently match returning users by email. With
  mutable emails, an email change on the provider side silently creates a duplicate user
  instead of matching. Should LDAP/social store a provider-uid → user mapping (User Social
  Login already does this for OAuth; LDAP has nothing)? IMO: yes for LDAP (map on the
  LDAP username/DN), keep email as fallback-with-warning.

## What this research is based on

- frappe `develop` at `aa56ab185b`, apps sampled: erpnext, hrms, crm, lms.
- Live-site schema/data checks (`SHOW INDEX FROM tabUser`, name/email divergence counts).
- Key files: `frappe/core/doctype/user/user.py`, `frappe/auth.py`,
  `frappe/utils/password.py`, `frappe/model/rename_doc.py`, `frappe/twofactor.py`,
  `frappe/utils/oauth.py`, `frappe/email/doctype/email_queue/email_queue.py`,
  `frappe/desk/doctype/notification_log/notification_log.py`.
