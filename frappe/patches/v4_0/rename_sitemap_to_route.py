import frappe

from frappe.model import rename_field

def execute():
	tables = frappe.db.sql_list("show tables")
	if "tabWebsite Route" not in tables:
		frappe.rename_doc("DocType", "Website Sitemap", "Website Route", force=True)

	if "tabWebsite Template" not in tables:
		frappe.rename_doc("DocType", "Website Sitemap Config", "Website Template", force=True)
		
	try:	
		if "tabWebsite Route Permission" not in tables:
			frappe.rename_doc("DocType", "Website Sitemap Permission", "Website Route Permission", force=True)
		
		for d in ("Blog Category", "Blog Post", "Web Page", "Website Route", "Website Group"):
			frappe.reload_doc("website", "doctype", frappe.scrub(d))
			rename_field(d, "parent_website_sitemap", "parent_website_route")
		
		rename_field("Website Route", "website_sitemap_config", "website_template")
		rename_field("Website Route Permission", "website_sitemap", "website_route")
	except Exception, e:
		if e.args[0] != 1054:
			raise

	for d in ("blog_category", "blog_post", "web_page", "website_route", "website_group"):
		frappe.reload_doc("website", "doctype", d)
