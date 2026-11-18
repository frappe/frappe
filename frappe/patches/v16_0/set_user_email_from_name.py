import frappe
from frappe import STANDARD_USERS, _
from frappe.query_builder.functions import Lower

# a standard user's default email, and the reserved address it moves to when a user's ID is that email
DEFAULT_EMAILS = {
	"Administrator": ("admin@example.com", "admin@frappe.invalid"),
	"Guest": ("guest@example.com", "guest@frappe.invalid"),
}


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

	# People sign up as admin@example.com: Administrator's (or Guest's) default email moves aside.
	standard_users_moved = {
		name: DEFAULT_EMAILS[name][1]
		for email, names in owners.items()
		if len(names) > 1
		for name in names
		if name in DEFAULT_EMAILS and email == DEFAULT_EMAILS[name][0]
	}

	# Rare: a user whose ID is Administrator's changed email, or, on Postgres, two IDs that differ
	# only in case (John@x.com and john@x.com).
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
