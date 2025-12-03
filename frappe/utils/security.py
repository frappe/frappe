import json

import frappe


@frappe.whitelist(allow_guest=True, methods=["POST"])
def csp_report():
	data = json.loads(frappe.request.get_data())
	body = data.get("body", {})
	doc = frappe.new_doc("Content Security Policy Report")
	doc.blocked_url = body.get("blockedURL")
	doc.column_number = body.get("columnNumber")
	doc.disposition = body.get("disposition")
	doc.document_url = body.get("documentURL")
	doc.effective_directive = body.get("effectiveDirective")
	doc.line_number = body.get("lineNumber")
	doc.original_policy = body.get("originalPolicy")
	doc.referrer = body.get("referrer")
	doc.sample = body.get("sample")
	doc.source_file = body.get("sourceFile")
	doc.status_code = body.get("statusCode")
	doc.url = data.get("url")
	doc.user_agent = data.get("user_agent")
	doc.save()
