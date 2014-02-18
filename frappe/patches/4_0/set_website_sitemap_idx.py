import frappe

def execute():
	frappe.conn.sql("""update `tabWebsite Sitemap` set idx=null""")
	# frappe.conn.sql("""update `tabWeb Page` set idx=null""")
	# frappe.conn.sql("""update `tabBlog Post` set idx=null""")
	# frappe.conn.sql("""update `tabBlog Category` set idx=null""")
	# frappe.conn.sql("""update `tabWebsite Group` set idx=null""")
	# frappe.conn.sql("""delete from `tabTable of Contents`""")

	for doctype in ["Blog Category", "Blog Post", "Web Page", "Website Group"]:
		for name in frappe.conn.get_values("Website Sitemap", {"ref_doctype":doctype}, "docname"):
			frappe.bean(doctype, name[0]).save()
		