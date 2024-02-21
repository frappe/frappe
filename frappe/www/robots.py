import frappe

base_template_path = "www/robots.txt"


def get_context(context):
	robots_txt = (
		frappe.db.get_single_value("Website Settings", "robots_txt")
		or (frappe.local.conf.robots_txt and frappe.read_file(frappe.local.conf.robots_txt))
		or ""
	)

	return {"robots_txt": robots_txt}
