import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
from frappe.utils import cint


def execute():
	"""Disable signups on sites that have them enabled only from the old default."""
	if cint(frappe.db.get_single_value("Website Settings", "disable_signup")):
		return

	if frappe.db.exists(
		"Version",
		{
			"ref_doctype": "Website Settings",
			"docname": "Website Settings",
			"data": ("like", "%disable_signup%"),
		},
	):
		return

	frappe.db.set_single_value("Website Settings", "disable_signup", 1)
	notify_system_managers()


def notify_system_managers():
	system_managers = frappe.get_all(
		"Has Role", filters={"role": "System Manager", "parenttype": "User"}, pluck="parent"
	)
	recipients = frappe.get_all(
		"User", filters={"name": ("in", system_managers), "enabled": 1}, pluck="email"
	)

	make_notification_logs(
		{
			"type": "Alert",
			"document_type": "Website Settings",
			"document_name": "Website Settings",
			"subject": _("Website signups are now disabled"),
			"email_content": _(
				"Signups were enabled by an old default setting, so anyone could create an account on this site. To allow signups again, clear Disable signups in Website Settings."
			),
		},
		recipients,
	)
