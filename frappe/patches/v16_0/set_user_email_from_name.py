import click

import frappe
from frappe import STANDARD_USERS, _
from frappe.query_builder.functions import Lower

DEFAULT_EMAILS = {"Administrator": "admin@example.com", "Guest": "guest@example.com"}
RESERVED_EMAILS = {"Administrator": "admin@frappe.invalid", "Guest": "guest@frappe.invalid"}


def execute():
	"""Set every user's email to their user ID in lowercase, so the email can be made unique."""
	users = frappe.get_all("User", fields=["name", "email"])
	user_ids = {user.name.lower(): user.name for user in users if user.name not in STANDARD_USERS}

	changes, standard_user_emails, owners = {}, {}, {}
	for user in users:
		if user.name in STANDARD_USERS:
			# Administrator and Guest keep their own email, lowercased, unless another user's ID is
			# that email: then they go back to their default one (people sign up as admin@example.com)
			email = (user.email or "").lower()
			if email in user_ids:
				email = DEFAULT_EMAILS[user.name]
				if email in user_ids:
					email = RESERVED_EMAILS[user.name]

			if email and email != user.email:
				standard_user_emails[user.name] = (user.email, email)
		else:
			email = user.name.lower()
			if email != user.email:
				changes[user.name] = user.email

		owners.setdefault((email or "").lower(), []).append(user.name)

	# Rare: an ID that is a reserved email, or, on Postgres, two IDs that differ only in case
	# (John@x.com and john@x.com). The unique index would fail on these, so stop with the names instead.
	clashes = {email: names for email, names in owners.items() if email and len(names) > 1}
	if clashes:
		frappe.throw(
			_(
				"These users would share an email: {0}. Change their emails so that each one is unique, then run migrate again."
			).format("; ".join(f"{email} ({', '.join(names)})" for email, names in clashes.items()))
		)

	User = frappe.qb.DocType("User")
	for name, (old_email, email) in standard_user_emails.items():
		frappe.qb.update(User).set(User.email, email).where(User.name == name).run()

		other_user = user_ids.get(old_email.lower())
		if name == "Administrator" and other_user and old_email.lower() != DEFAULT_EMAILS[name]:
			report_administrator_email_change(old_email, email, other_user)
		elif other_user:
			click.echo(
				f"User {name}: email {old_email!r} changed to {email!r}, another user has it as their ID"
			)
		else:
			click.echo(f"User {name}: email {old_email!r} changed to {email!r}")

	if not changes:
		return

	for name, email in changes.items():
		click.echo(f"User {name}: email {email!r} changed to {name.lower()!r}")

	frappe.qb.update(User).set(User.email, Lower(User.name)).where(User.name.isin(list(changes))).run()


def report_administrator_email_change(old_email, new_email, other_user):
	"""Tell System Managers that Administrator's email changed, and how to sign in if 2FA needs it."""
	from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
	from frappe.twofactor import get_verification_method, two_factor_is_enabled
	from frappe.utils.user import get_system_managers

	subject = _("Administrator's email changed from {0} to {1}, because {2} has the same email.").format(
		old_email, new_email, other_user
	)
	if two_factor_is_enabled("Administrator") and get_verification_method() != "SMS":
		details = _(
			"Administrator uses two-factor authentication, which can email it a code, so it may not be able to sign in until it has a real address. Sign in as Administrator without 2FA (e.g. {0}) and give it another address, such as {1}."
		).format(
			f"bench --site {frappe.local.site} browse --user Administrator",
			old_email.replace("@", "+admin@", 1),
		)
	else:
		details = _("Administrator won't get mail until it has a real address.")

	message = f"{subject} {details}"
	click.secho(message, fg="red")

	make_notification_logs(
		{"type": "Alert", "subject": subject, "email_content": message}, get_system_managers(only_name=True)
	)
