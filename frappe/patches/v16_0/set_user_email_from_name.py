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
	clashes_with_users = {}
	for user in users:
		if user.name in STANDARD_USERS:
			# Administrator and Guest keep their own email, lowercased, unless another user's ID is
			# that email: then they go back to their default one (people sign up as admin@example.com)
			email = (user.email or "").lower()
			if email in user_ids:
				clashes_with_users[user.name] = (user.email, user_ids[email])
				email = DEFAULT_EMAILS[user.name]
				if email in user_ids:
					email = RESERVED_EMAILS[user.name]

			if email and email != user.email:
				standard_user_emails[user.name] = email
		else:
			email = user.name.lower()
			if email != user.email:
				changes[user.name] = user.email

		owners.setdefault((email or "").lower(), []).append(user.name)

	# Rare: on Postgres, two IDs that differ only in case (John@x.com and john@x.com).
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
		frappe.qb.update(User).set(User.email, email).where(User.name == name).run()

		if name not in clashes_with_users:
			click.echo(f"User {name}: email changed to {email!r}")
			continue

		old_email, other_user = clashes_with_users[name]
		if name == "Administrator" and old_email.lower() != DEFAULT_EMAILS[name]:
			report_administrator_email_change(old_email, other_user, email)
		else:
			click.echo(
				_("{0}'s email changed from {1} to {2}, because {3} has the same email.").format(
					name, old_email, email, other_user
				)
			)

	if not changes:
		return

	for name, email in changes.items():
		click.echo(f"User {name}: email {email!r} changed to {name.lower()!r}")

	frappe.qb.update(User).set(User.email, Lower(User.name)).where(User.name.isin(list(changes))).run()


def report_administrator_email_change(old_email, other_user, new_email):
	"""Tell System Managers that Administrator's email changed, and how to sign in if 2FA needs it."""
	from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
	from frappe.twofactor import get_verification_method, two_factor_is_enabled
	from frappe.utils.user import get_system_managers

	subject = _("Administrator's email changed from {0} to {1}, because {2} has the same email.").format(
		old_email, new_email, other_user
	)
	if two_factor_is_enabled("Administrator") and get_verification_method() != "SMS":
		local_part, _at, domain = old_email.rpartition("@")
		details = _(
			"Administrator uses two-factor authentication, which can email it a code, so it may not be able to sign in until it has a real address. Sign in as Administrator without 2FA (e.g. {0}) and give it another address, such as {1}."
		).format(
			f"bench --site {frappe.local.site} browse --user Administrator",
			f"{local_part}+admin@{domain}" if local_part else _("a plus-address of your own"),
		)
	else:
		details = _("Administrator won't get mail until it has a real address.")

	message = f"{subject} {details}"
	click.secho(message, fg="red")

	make_notification_logs(
		{"type": "Alert", "subject": subject, "email_content": message}, get_system_managers(only_name=True)
	)
