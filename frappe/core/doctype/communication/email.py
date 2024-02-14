from frappe.communications.doctype.communication.email import (
	_make,
	_mark_email_as_seen,
	add_attachments,
	make,
	mark_email_as_seen,
	set_incoming_outgoing_accounts,
	update_communication_as_read,
	validate_email,
)
from frappe.utils.deprecations import deprecated

make = deprecated(make, "frappe.communications.doctype.communication.email.make")
_make = deprecated(_make, "frappe.communications.doctype.communication.email._make")
validate_email = deprecated(
	validate_email, "frappe.communications.doctype.communication.email.validate_email"
)
set_incoming_outgoing_accounts = deprecated(
	set_incoming_outgoing_accounts,
	"frappe.communications.doctype.communication.email.set_incoming_outgoing_accounts",
)
add_attachments = deprecated(
	add_attachments, "frappe.communications.doctype.communication.email.add_attachments"
)
mark_email_as_seen = deprecated(
	mark_email_as_seen, "frappe.communications.doctype.communication.email.mark_email_as_seen"
)
_mark_email_as_seen = deprecated(
	_mark_email_as_seen, "frappe.communications.doctype.communication.email._mark_email_as_seen"
)
update_communication_as_read = deprecated(
	update_communication_as_read,
	"frappe.communications.doctype.communication.email.update_communication_as_read",
)
