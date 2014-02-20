import frappe

def execute():
	from frappe.website.doctype.website_sitemap_config.website_sitemap_config import \
		get_pages_and_generators, get_template_controller


	for app in frappe.get_installed_apps():
		pages, generators = get_pages_and_generators(app)
		for g in generators:
			doctype = frappe.get_attr(get_template_controller(app, g[2], g[3]) + ".doctype")
			module = frappe.conn.get_value("DocType", doctype, "module")
			frappe.reload_doc(module, "doctype", doctype)
		
	frappe.conn.sql("""update `tabWebsite Sitemap` set idx=null""")
	for doctype in ["Blog Category", "Blog Post", "Web Page", "Website Group"]:
		frappe.conn.sql("""update `tab{}` set idx=null""".format(doctype))

	from frappe.website.doctype.website_sitemap_config.website_sitemap_config import rebuild_website_sitemap_config
	rebuild_website_sitemap_config()