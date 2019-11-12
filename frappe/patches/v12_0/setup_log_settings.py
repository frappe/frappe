import frappe

def execute():
	doc = frappe.get_single("Log Settings")
	for doctype in frappe.get_all("DocType", filters={"istable": 0, "issingle": 0, "name": ('like', '%Log')}):
		doc.append("log_settings", {
			"ref_doctype": doctype.name,
			"log_days": 30
		})
	doc.save()