from frappe.communications.doctype.communication.communication import (
	Communication,
	add_contact_links_to_communication,
	get_contacts,
	get_email_without_link,
	get_emails,
	get_permission_query_conditions_for_communication,
	has_permission,
	parse_email,
	set_avg_response_time,
	update_first_response_time,
	update_parent_document_on_communication,
)
from frappe.utils.deprecations import deprecated

Communication.__new__ = deprecated(
	Communication.__new__, "frappe.communications.doctype.communication.communication.Communication"
)
has_permission = deprecated(
	has_permission, "frappe.communications.doctype.communication.communication.has_permission"
)
get_permission_query_conditions_for_communication = deprecated(
	get_permission_query_conditions_for_communication,
	"frappe.communications.doctype.communication.communication.get_permission_query_conditions_for_communication",
)
get_contacts = deprecated(
	get_contacts, "frappe.communications.doctype.communication.communication.get_contacts"
)
get_emails = deprecated(get_emails, "frappe.communications.doctype.communication.communication.get_emails")
add_contact_links_to_communication = deprecated(
	add_contact_links_to_communication,
	"frappe.communications.doctype.communication.communication.add_contact_links_to_communication",
)
parse_email = deprecated(parse_email, "frappe.communications.doctype.communication.communication.parse_email")
get_email_without_link = deprecated(
	get_email_without_link, "frappe.communications.doctype.communication.communication.get_email_without_link"
)
update_parent_document_on_communication = deprecated(
	update_parent_document_on_communication,
	"frappe.communications.doctype.communication.communication.update_parent_document_on_communication",
)
update_first_response_time = deprecated(
	update_first_response_time,
	"frappe.communications.doctype.communication.communication.update_first_response_time",
)
set_avg_response_time = deprecated(
	set_avg_response_time, "frappe.communications.doctype.communication.communication.set_avg_response_time"
)
