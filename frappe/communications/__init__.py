# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.communications.doctype.communication.communication import Communication

from .interfaces import OutgoingCommunicationHandler


@frappe.whitelist()
def send(
	cls: OutgoingCommunicationHandler | str,
	comm: Communication,
	name: str | None = None,
	log: bool = True,
	ignore_permissions: bool = False,
):
	"""
	Entrypoint for sending communications.

	:param cls: pass a specific handler class, e.g. from hooks or as string from javascript
	:param comm: the communcation document
	:param name: the document name of the handler
	             if the handler is a singleton document, no name is set
	             if the handler is a bridging document, such as a log or queue, no name is set either
	:param log:  save the communcation after sending
	:param ignore_permissions: whether to ignore if the user has permission to send communication
	             for this particular medium on this particular document
	"""
	if isinstance(cls, str):
		cls = frappe.get_attr(cls)

	assert issubclass(cls, OutgoingCommunicationHandler),
		f"{cls} must be a subclass of frappe.communications.interfaces.OutgoingCommunicationHandler"

	assert isinstance(comm, Communication),
		f"{comm} must be an instance of the Communication doctype"

	assert comm.reference_doctype is not None,
		f"{comm} must have the 'reference_doctype' set"

	assert comm.reference_docname is not None,
		f"{comm} must have the 'reference_docname' set"

	return cls.send(comm, name, log)
