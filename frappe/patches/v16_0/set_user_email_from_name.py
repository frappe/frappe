import frappe
from frappe import STANDARD_USERS, _
from frappe.query_builder.functions import Lower


def execute():
	"""Set every user's email to their user ID in lowercase, so the email can be made unique."""
	users = frappe.get_all("User", fields=["name", "email"])

	# Administrator and Guest keep their own email; every other user gets their ID
	owners = {}
	for user in users:
		email = user.email if user.name in STANDARD_USERS else user.name
		owners.setdefault((email or "").lower(), []).append(user.name)

	# Rare: a user whose ID is Administrator's or Guest's email (e.g. admin@example.com),
	# or, on Postgres, two IDs that differ only in case (John@x.com and john@x.com).
	# The unique index would fail on these, so stop with the names instead.
	clashes = [names for email, names in owners.items() if email and len(names) > 1]
	if clashes:
		frappe.throw(
			_(
				"These users would have the same email: {0}. Change one of them, then run migrate again."
			).format("; ".join(", ".join(names) for names in clashes))
		)

	# Usually the email already equals the ID; print only the rows that change
	for user in users:
		if user.name not in STANDARD_USERS and user.email != user.name.lower():
			print(f"User {user.name}: email {user.email!r} changed to {user.name.lower()!r}")

	User = frappe.qb.DocType("User")
	frappe.qb.update(User).set(User.email, Lower(User.name)).where(User.name.notin(STANDARD_USERS)).run()
