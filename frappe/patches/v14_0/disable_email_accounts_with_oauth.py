import frappe
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs


def execute():
	if frappe.get_all("Email Account", {"auth_method": "OAuth", "connected_user": ["is", "set"]}, limit=1):
		return

	# Setting awaiting password to 1 for email accounts where Oauth is enabled.
	# This is done so that people can resetup their email accounts with connected app mechanism.
	frappe.db.set_value("Email Account", {"auth_method": "OAuth"}, "awaiting_password", 1)

	message = "Email Accounts with auth method as OAuth have been disabled.\
	Please re-setup your OAuth based email accounts with the connected app mechanism to re-enable them."

	if sysmanagers := get_system_managers():
		make_notification_logs(
			{
				"type": "Alert",
				"subject": frappe._(message),
			},
			sysmanagers,
		)


def get_system_managers():
	user_doctype = frappe.qb.DocType("User").as_("user")
	user_role_doctype = frappe.qb.DocType("Has Role").as_("user_role")
	return (
		frappe.qb.from_(user_doctype)
		.from_(user_role_doctype)
		.select(user_doctype.email)
		.where(user_role_doctype.role == "System Manager")
		.where(user_doctype.enabled == 1)
		.where(user_role_doctype.parent == user_doctype.name)
	).run(pluck=True)
