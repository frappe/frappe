import frappe
from frappe import STANDARD_USERS

# Framework defaults, restored to a standard user when its address is handed to a real user.
STANDARD_USER_DEFAULT_EMAIL = {
	"Administrator": "admin@example.com",
	"Guest": "guest@example.com",
}


def execute():
	"""Deduplicate `User.email` so a unique index can be enforced on it.

	`email` is being promoted from a decorative field (today it is just a copy of the primary
	key) into the login key, which needs a unique index. Real sites have accumulated drift --
	case variants, blanks, and outright duplicates -- so this cleans the data first; the unique
	index itself is added by the model sync from `unique: 1` in `user.json`, which runs right
	after this pre-model-sync patch.

	Contract (see user_id.md):
	  - Best effort: never raises. A row that cannot be written is logged and skipped rather
	    than aborting the whole `bench migrate`.
	  - Idempotent: a second run over already-unique data changes nothing.

	Dedup strategy, per group of users sharing one (normalized) email:
	  1. A winner keeps the address -- preferring the enabled account whose name IS the email
	     (the grandfathered login), then any enabled real user, then any real user.
	  2. Standard users (Administrator/Guest) surrender their address to a real user and fall
	     back to their framework default, or a ``+tag`` variant if that also collides.
	  3. Every other losing account is re-addressed from its own login name where that is an
	     email, otherwise via ``+tag`` addressing -- always kept globally unique.
	"""
	users = frappe.get_all("User", fields=["name", "email", "enabled"], order_by="creation asc")

	# Apply. Guard each write so a single bad row can't abort the patch.
	applied = 0
	changes = plan_dedupe(users)
	for name, _old_email, new_email in changes:
		try:
			frappe.db.set_value("User", name, "email", new_email, update_modified=False)
			applied += 1
		except Exception:
			frappe.log_error(title="User email dedupe failed", message=frappe.get_traceback())

	frappe.db.commit()
	_report(changes, applied)


def plan_dedupe(users: list) -> list[tuple[str, str, str]]:
	"""Pure planning step: given user rows (dicts with name/email/enabled), return the list of
	``(name, old_email, new_email)`` rewrites needed to make every email unique. No IO -- so it
	is unit-testable and lets us assert idempotency (re-planning its own output yields nothing).
	"""
	# Group by the normalized (strip + lowercase) email -- the form a ci unique index compares.
	groups: dict[str, list] = {}
	for user in users:
		groups.setdefault(_normalize(user["email"]), []).append(user)

	used: set[str] = set()  # every address already claimed, to keep new ones globally unique
	changes: list[tuple[str, str, str]] = []

	# Pass 1 -- keepers. Each non-empty group keeps exactly one address; the rest are losers.
	losers = []
	for key, members in groups.items():
		if not key:
			# No usable address at all -> every such user needs a fresh, unique one.
			losers.extend(members)
			continue

		winner = _pick_winner(members)
		used.add(key)
		if winner["email"] != key:
			# Normalize the kept address even when it was already unique (e.g. mixed case).
			changes.append((winner["name"], winner["email"], key))
		losers.extend(m for m in members if m["name"] != winner["name"])

	# Pass 2 -- rewrite every loser to a unique address.
	for loser in losers:
		new_email = _resolve_unique(loser, used)
		used.add(new_email)
		if new_email != loser["email"]:
			changes.append((loser["name"], loser["email"], new_email))

	return changes


def _normalize(email: str | None) -> str:
	return (email or "").strip().lower()


def _pick_winner(members: list):
	"""Pick the user that keeps the shared address. Higher tuple sorts first under ``max``:
	real-user > standard-user, then enabled > disabled, then name-is-email > not. Ties resolve
	to the earliest-created member, since ``members`` is ordered by creation."""

	def rank(u):
		return (
			u["name"] not in STANDARD_USERS,
			bool(u["enabled"]),
			_normalize(u["name"]) == _normalize(u["email"]),
		)

	return max(members, key=rank)


def _resolve_unique(user, used: set[str]) -> str:
	"""Compute a unique replacement address for a losing account."""
	if user["name"] in STANDARD_USERS:
		# Restore the framework default; +tag it below if a real user now owns that address.
		base = STANDARD_USER_DEFAULT_EMAIL[user["name"]]
	elif "@" in (user["name"] or ""):
		# Grandfathered real user: its name is the authoritative login -> re-address to it.
		base = _normalize(user["name"])
	else:
		# Series-named or blank account: derive from the address it was fighting over.
		base = _normalize(user["email"]) or "user@example.com"

	if base not in used:
		return base

	return _plus_address(base, _tag(user["name"]), used)


def _plus_address(email: str, tag: str, used: set[str]) -> str:
	"""Build a unique ``local+tag@domain`` variant of ``email``."""
	local, _, domain = email.rpartition("@")
	if not local:
		local, domain = "user", "example.com"
	local = local.split("+", 1)[0]  # avoid stacking +tags if this ever re-runs on a +variant

	candidate = f"{local}+{tag}@{domain}"
	suffix = 1
	while candidate in used:
		candidate = f"{local}+{tag}{suffix}@{domain}"
		suffix += 1
	return candidate


def _tag(name: str | None) -> str:
	"""A lowercase, alphanumeric token from the user name, safe for +tag addressing."""
	token = "".join(c for c in (name or "") if c.isalnum()).lower()
	return (token or "user")[:30]


def _report(changes: list, applied: int) -> None:
	if not changes:
		print("User email dedupe: no duplicate/divergent emails found; nothing to change.")
		return

	print(f"User email dedupe: rewrote {applied} of {len(changes)} email(s) to enforce uniqueness:")
	for name, old, new in changes:
		print(f"  {name}: {old!r} -> {new!r}")
