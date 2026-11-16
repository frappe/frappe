import frappe
from frappe import STANDARD_USERS, _
from frappe.query_builder.functions import Lower


def execute():
	"""Set every user's email to their user ID in lowercase, so the email can be made unique."""
	users = frappe.get_all("User", fields=["name", "email"])

	changes, owners = {}, {}
	for user in users:
		# Administrator and Guest keep their own email
		email = user.email if user.name in STANDARD_USERS else user.name.lower()
		if email != user.email:
			changes[user.name] = user.email

		owners.setdefault((email or "").lower(), []).append(user.name)

	# Rare: a user whose ID is Administrator's or Guest's email (e.g. admin@example.com),
	# or, on Postgres, two IDs that differ only in case (John@x.com and john@x.com).
	# The unique index would fail on these, so stop with the names instead.
	clashes = [names for email, names in owners.items() if email and len(names) > 1]
	if clashes:
		frappe.throw(
			_(
				"These users would share an email: {0}. Change their emails so that each one is unique, then run migrate again."
			).format("; ".join(", ".join(names) for names in clashes))
		)

	if not changes:
		return

	for name, email in changes.items():
		print(f"User {name}: email {email!r} changed to {name.lower()!r}")

	User = frappe.qb.DocType("User")
	frappe.qb.update(User).set(User.email, Lower(User.name)).where(User.name.isin(list(changes))).run()
