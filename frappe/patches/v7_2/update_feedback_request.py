from __future__ import unicode_literals
import frappe

def execute():
	"""
		rename feedback request documents,
		update the feedback request and save the rating and communication
		reference in Feedback Request document
	"""

	frappe.reload_doc("core", "doctype", "feedback_request")
	feedback_requests = frappe.get_all("Feedback Request")
	for request in feedback_requests:
		communication, rating = frappe.db.get_value("Communication", { "feedback_request": request.get("name") },
			["name", "rating"]) or [None, 0]

		if communication:
			frappe.db.sql("""update `tabFeedback Request` set reference_communication='{communication}',
				rating={rating} where name='{feedback_request}'""".format(
					communication=communication,
					rating=rating or 0,
					feedback_request=request.get("name")
			))

		if "Feedback" not in request.get("name"):
			# rename the feedback request doc
			reference_name, creation = frappe.db.get_value("Feedback Request", request.get("name"), ["name", "creation"])
			oldname = request.get("name")
			newname = "Feedback for {doctype} {docname} on {datetime}".format(
				doctype="Feedback Request",
				docname=reference_name,
				datetime=creation
			)
			frappe.rename_doc("Feedback Request", oldname, newname, ignore_permissions=True)
			if communication: frappe.db.set_value("Communication", communication, "feedback_request", newname)