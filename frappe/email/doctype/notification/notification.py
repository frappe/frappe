from frappe.communications.doctype.notification.notification import (
	Notification,
	evaluate_alert,
	get_assignees,
	get_context,
	get_documents_for_today,
	get_emails_from_template,
	trigger_daily_alerts,
	trigger_notifications,
)
from frappe.utils.deprecations import deprecated

Notification.__new__ = deprecated(
	Notification.__new__, "frappe.communications.doctype.notification.notification.Notification"
)
get_documents_for_today = deprecated(
	get_documents_for_today,
	"frappe.communications.doctype.notification.notification.get_emails_from_template",
)
trigger_daily_alerts = deprecated(
	trigger_daily_alerts, "frappe.communications.doctype.notification.notification.get_emails_from_template"
)
trigger_notifications = deprecated(
	trigger_notifications, "frappe.communications.doctype.notification.notification.get_emails_from_template"
)
evaluate_alert = deprecated(
	evaluate_alert, "frappe.communications.doctype.notification.notification.get_emails_from_template"
)
get_context = deprecated(
	get_context, "frappe.communications.doctype.notification.notification.get_emails_from_template"
)
get_assignees = deprecated(
	get_assignees, "frappe.communications.doctype.notification.notification.get_emails_from_template"
)
get_emails_from_template = deprecated(
	get_emails_from_template,
	"frappe.communications.doctype.notification.notification.get_emails_from_template",
)
