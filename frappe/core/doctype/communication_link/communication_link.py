from frappe.communications.doctype.communication_link.communication_link import (
	CommunicationLink,
)
from frappe.utils.deprecations import deprecated

CommunicationLink.__new__ = deprecated(
	CommunicationLink.__new__,
	"frappe.communications.doctype.communication_link.communication_link.CommunicationLink",
)
