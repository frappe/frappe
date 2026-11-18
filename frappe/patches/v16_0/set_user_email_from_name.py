import frappe
from frappe import STANDARD_USERS, _
from frappe.query_builder.functions import Lower

RESERVED_EMAILS = {"Administrator": "admin@frappe.invalid", "Guest": "guest@frappe.invalid"}


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

	# A user whose ID is Administrator's or Guest's email (people sign up as admin@example.com):
	# the standard user's email moves to a reserved address.
	standard_users_moved = {
		name: RESERVED_EMAILS[name]
		for email, names in owners.items()
		if email and len(names) > 1
		for name in names
		if name in STANDARD_USERS
	}

	# Rare: on Postgres, two IDs that differ only in case (John@x.com and john@x.com).
	# The unique index would fail on these, so stop with the names instead.
	clashes = [
		names
		for email, names in owners.items()
		if email and len([name for name in names if name not in standard_users_moved]) > 1
	]
	if clashes:
		frappe.throw(
			_(
				"These users would share an email: {0}. Change their emails so that each one is unique, then run migrate again."
			).format("; ".join(", ".join(names) for names in clashes))
		)

	User = frappe.qb.DocType("User")
	for name, email in standard_users_moved.items():
		print(f"User {name}: email changed to {email!r}, another user's ID is its email")
		frappe.qb.update(User).set(User.email, email).where(User.name == name).run()

	if not changes:
		return

	for name, email in changes.items():
		print(f"User {name}: email {email!r} changed to {name.lower()!r}")

	frappe.qb.update(User).set(User.email, Lower(User.name)).where(User.name.isin(list(changes))).run()
