from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.core.doctype.feedback_request.feedback_request import is_valid_feedback_request

no_cache = True

def get_context(context):
	reference_doctype = frappe.form_dict.get("reference_doctype")
	reference_name = frappe.form_dict.get("reference_name")

	if not all([reference_name, reference_doctype]) or \
		not frappe.db.get_value(reference_doctype, reference_name):
		
		return {
			"is_valid_request": False,
			"error_message": "Invalid reference doctype and reference name"
		}

	communications = frappe.get_all("Communication", filters={
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
		"communication_type": "Communication"	
	}, fields=["*"], limit_page_length=10, order_by="creation desc")

	return {
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
		"comment_list": communications,
		"is_communication": True,
		"is_valid_request": True
	}

@frappe.whitelist(allow_guest=True)
def accept(key, sender, reference_doctype, reference_name, feedback, rating, fullname):
	""" save the feedback in communication """
	if not reference_doctype and not reference_name or \
		not frappe.db.get_value(reference_doctype, reference_name):

		frappe.throw(_("Invalid Reference"))

	if not rating:
		frappe.throw(_("Please add a rating"))

	if not is_valid_feedback_request(key):
		frappe.throw(_("Expired link"))

	try:
		feedback_request = frappe.db.get_value("Feedback Request", {"key": key})

		communication = frappe.get_doc({
			"rating": rating,
			"status": "Closed",
			"content": feedback or "",
			"doctype": "Communication",
			"sender": sender or "Guest",
			"sent_or_received": "Received",
			"communication_type": "Feedback",
			"reference_name": reference_name,
			"sender_full_name": fullname or "",
			"feedback_request": feedback_request,
			"reference_doctype": reference_doctype,
			"subject": "Feedback for {0} {1}".format(reference_doctype, reference_name),
		}).insert(ignore_permissions=True)

		doc = frappe.get_doc("Feedback Request", feedback_request)
		doc.is_feedback_submitted = 1
		doc.rating = rating
		doc.reference_communication = communication.name
		doc.save(ignore_permissions=True)
		return True
	except Exception:
		frappe.log_error()
		frappe.throw(_("Cannot submit feedback, please try again later"))
