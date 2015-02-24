from __future__ import unicode_literals
import frappe

def execute():
	pass
	# from frappe.website.doctype.website_template.website_template import \
	# 	get_pages_and_generators, get_template_controller
	#
	# frappe.reload_doc("website", "doctype", "website_template")
	# frappe.reload_doc("website", "doctype", "website_route")
	#
	# for app in frappe.get_installed_apps():
	# 	pages, generators = get_pages_and_generators(app)
	# 	for g in generators:
	# 		doctype = frappe.get_attr(get_template_controller(app, g["path"], g["fname"]) + ".doctype")
	# 		module = frappe.db.get_value("DocType", doctype, "module")
	# 		frappe.reload_doc(frappe.scrub(module), "doctype", frappe.scrub(doctype))
	#
	# frappe.db.sql("""update `tabBlog Category` set `title`=`name` where ifnull(`title`, '')=''""")
	# frappe.db.sql("""update `tabWebsite Route` set idx=null""")
	# for doctype in ["Blog Category", "Blog Post", "Web Page", "Website Group"]:
	# 	frappe.db.sql("""update `tab{}` set idx=null""".format(doctype))
	#
	# from frappe.website.doctype.website_template.website_template import rebuild_website_template
	# rebuild_website_template()
