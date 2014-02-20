import frappe

def execute():
	frappe.conn.sql("""update `tabWebsite Sitemap` set idx=null""")
	for doctype in ["Blog Category", "Blog Post", "Web Page", "Website Group"]:
		frappe.conn.sql("""update `tab{}` set idx=null""".format(doctype))

	from frappe.website.doctype.website_sitemap_config.website_sitemap_config import rebuild_website_sitemap_config
	rebuild_website_sitemap_config()