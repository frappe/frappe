# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE
import frappe
from tenacity import retry, retry_if_exception_type, stop_after_attempt
from frappe.model.document import Document


class AccessLog(Document):
	pass


@frappe.whitelist()
@frappe.write_only()
@retry(
	stop=stop_after_attempt(3), retry=retry_if_exception_type(frappe.DuplicateEntryError)
)
def make_access_log(
	doctype=None,
	document=None,
	method=None,
	file_type=None,
	report_name=None,
	filters=None,
	page=None,
	columns=None,
):

	user = frappe.session.user
	in_request = frappe.request and frappe.request.method == "GET"

	doc = frappe.get_doc(
		{
			"doctype": "Access Log",
			"user": user,
			"export_from": doctype,
			"reference_document": document,
			"file_type": file_type,
			"report_name": report_name,
			"page": page,
			"method": method,
			"filters": frappe.utils.cstr(filters) if filters else None,
			"columns": columns,
		}
	)
	doc.insert(ignore_permissions=True)

	# `frappe.db.commit` added because insert doesnt `commit` when called in GET requests like `printview`
	# dont commit in test mode
	if not frappe.flags.in_test or in_request:
		frappe.db.commit()
