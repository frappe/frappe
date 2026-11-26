import click

import frappe
from frappe import STANDARD_USERS, _
from frappe.query_builder.functions import Lower

DEFAULT_EMAILS = {"Administrator": "admin@example.com", "Guest": "guest@example.com"}
RESERVED_EMAILS = {"Administrator": "admin@frappe.invalid", "Guest": "guest@frappe.invalid"}


def execute():
	"""Set every user's email to their user ID in lowercase, so the email can be made unique."""
	users = frappe.get_all("User", fields=["name", "email"])
	user_ids = {user.name.lower() for user in users if user.name not in STANDARD_USERS}

	changes, standard_user_emails, owners = {}, {}, {}
	for user in users:
		if user.name in STANDARD_USERS:
			# Administrator and Guest keep their own email, lowercased, unless it is the default
			# one and a user signed up with it (people sign up as admin@example.com)
			email = (user.email or "").lower()
			if email == DEFAULT_EMAILS[user.name] and email in user_ids:
				email = RESERVED_EMAILS[user.name]

			if email and email != user.email:
				standard_user_emails[user.name] = email
		else:
			email = user.name.lower()
			if email != user.email:
				changes[user.name] = user.email

		owners.setdefault((email or "").lower(), []).append(user.name)

	# Rare: a user whose ID is Administrator's or Guest's changed email, or, on Postgres,
	# two IDs that differ only in case (John@x.com and john@x.com).
	# The unique index would fail on these, so stop with the names instead.
	clashes = [names for email, names in owners.items() if email and len(names) > 1]
	if clashes:
		frappe.throw(
			_(
				"These users would share an email: {0}. Change their emails so that each one is unique, then run migrate again."
			).format("; ".join(", ".join(names) for names in clashes))
		)

	User = frappe.qb.DocType("User")
	for name, email in standard_user_emails.items():
		if email == RESERVED_EMAILS[name]:
			click.echo(f"User {name}: email changed to {email!r}, another user's ID is its default email")
		else:
			click.echo(f"User {name}: email changed to {email!r}")

		frappe.qb.update(User).set(User.email, email).where(User.name == name).run()

	if not changes:
		return

	for name, email in changes.items():
		click.echo(f"User {name}: email {email!r} changed to {name.lower()!r}")

	frappe.qb.update(User).set(User.email, Lower(User.name)).where(User.name.isin(list(changes))).run()
