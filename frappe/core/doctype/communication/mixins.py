from frappe.communications.doctype.communication.mixin import (
	CommunicationEmailMixin,
)
from frappe.utils.deprecations import deprecated

CommunicationEmailMixin.__new__ = deprecated(
	CommunicationEmailMixin.__new__,
	"frappe.communications.doctype.communication.mixin.CommunicationEmailMixin",
)
