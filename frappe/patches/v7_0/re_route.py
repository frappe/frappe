import frappe

def execute():
	update_routes(['Blog Post', 'Blog Category', 'Web Page'])

def update_routes(doctypes):
	"""Patch old routing system"""
	for d in doctypes:
		frappe.reload_doctype(d)
		try:
			frappe.db.sql("""update `tab{0}` set route = concat(ifnull(parent_website_route, ""),
				if(ifnull(parent_website_route, "")="", "", "/"), page_name)""".format(d))
		except Exception, e:
			if e.args[0]!=1054: raise e
