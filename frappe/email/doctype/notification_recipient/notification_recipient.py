from frappe.communications.doctype.notification_recipient.notification_recipient import (
	NotificationRecipient,
)
from frappe.utils.deprecations import deprecated

NotificationRecipient.__new__ = deprecated(
	NotificationRecipient.__new__,
	"frappe.communications.doctype.notification_recipient.notification_recipient.NotificationRecipient",
)
