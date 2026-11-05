import frappe
from frappe import STANDARD_USERS, _
from frappe.query_builder.functions import Lower
from frappe.utils import validate_email_address


def execute():
	"""Set every user's email to their user ID in lowercase, so the email can be made unique."""
	users = frappe.get_all("User", fields=["name", "email"])

	# Administrator, Guest and users whose ID is not an email keep their own email
	changes, kept, owners = {}, [], {}

	for user in users:
		email = user.email

		if validate_email_address(user.name):
			email = user.name.lower()
		elif user.name not in STANDARD_USERS:
			kept.append(user)

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
				"These users would have the same email: {0}. Change one of them, then run migrate again."
			).format("; ".join(", ".join(names) for names in clashes))
		)

	for user in kept:
		print(f"User {user.name}: ID is not an email, email {user.email!r} kept")

	if not changes:
		return

	for name, email in changes.items():
		print(f"User {name}: email {email!r} changed to {name.lower()!r}")

	User = frappe.qb.DocType("User")
	frappe.qb.update(User).set(User.email, Lower(User.name)).where(User.name.isin(list(changes))).run()
