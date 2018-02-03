from __future__ import unicode_literals
import frappe

from frappe.model.utils.rename_field import rename_field

def execute():
	tables = frappe.db.sql_list("show tables")
	for doctype in ("Website Sitemap", "Website Sitemap Config"):
		if "tab{}".format(doctype) in tables:
			frappe.delete_doc("DocType", doctype, force=1)
			frappe.db.sql("drop table `tab{}`".format(doctype))

	for d in ("Blog Category", "Blog Post", "Web Page"):
		frappe.reload_doc("website", "doctype", frappe.scrub(d))
		rename_field_if_exists(d, "parent_website_sitemap", "parent_website_route")

	for d in ("blog_category", "blog_post", "web_page", "post", "user_vote"):
		frappe.reload_doc("website", "doctype", d)

def rename_field_if_exists(doctype, old_fieldname, new_fieldname):
	try:
		rename_field(doctype, old_fieldname, new_fieldname)
	except Exception as e:
		if e.args[0] != 1054:
			raise
