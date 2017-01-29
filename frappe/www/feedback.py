import frappe
from frappe.core.doctype.feedback_request.feedback_request import is_valid_feedback_request

@frappe.whitelist(allow_guest=True)
def accept(key, sender, reference_doctype, reference_name, feedback, rating):
	""" save the feedback in communication """
	if not reference_doctype and not reference_name:
		frappe.throw("Invalid Reference Doctype, Reference Name")

	if not is_valid_feedback_request(key):
		frappe.throw("Link is Expired")

	frappe.get_doc({
		"rating": rating,
		"sender": sender,
		"status": "Closed",
		"feedback": feedback,
		"feedback_request": key,
		"doctype": "Communication",
		"sent_or_received": "Received",
		"communication_type": "Feedback",
		"reference_name": reference_name,
		"reference_doctype": reference_doctype,
		"subject": "Feedback for {0} {1}".format(reference_doctype, reference_name),
	}).insert(ignore_permissions=True)

	frappe.db.set_value("Feedback Request", key, "is_feedback_submitted", 1)
	return True