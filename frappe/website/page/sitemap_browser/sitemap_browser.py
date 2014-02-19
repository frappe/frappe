# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.website.render import clear_cache

@frappe.whitelist()
def get_children(parent=None):
	if not frappe.has_permission("Website Sitemap"):
		raise frappe.PermissionError
		
	if parent=="Sitemap":
		parent = ""

	return frappe.conn.sql("""select name as value, 1 as expandable from `tabWebsite Sitemap` where 
		ifnull(parent_website_sitemap, '')=%s and idx is not null order by -idx desc""", parent, as_dict=True)
		
@frappe.whitelist()
def move(name, up_or_down):
	ret = None
	if not frappe.has_permission("Website Sitemap"):
		raise frappe.PermissionError

	sitemap = frappe.doc("Website Sitemap", name)
	if up_or_down=="up":
		if sitemap.idx > 0:
			prev = frappe.doc("Website Sitemap", {
				"parent_website_sitemap": sitemap.parent_website_sitemap,
				"idx": sitemap.idx - 1
			})
			if prev.name:
				prev.idx = prev.idx + 1
				prev.save()
				
				sitemap.idx = sitemap.idx - 1
				sitemap.save()
				ret = "ok"

	else:
		nexts = frappe.doc("Website Sitemap", {
			"parent_website_sitemap": sitemap.parent_website_sitemap,
			"idx": sitemap.idx + 1
		})
		if nexts.name:
			nexts.idx = nexts.idx - 1
			nexts.save()
			
			sitemap.idx = sitemap.idx + 1
			sitemap.save()
			ret = "ok"

	clear_cache()
	return ret
	
@frappe.whitelist()
def update_parent(name, new_parent):
	if not frappe.has_permission("Website Sitemap"):
		raise frappe.PermissionError
	
	sitemap = frappe.doc("Website Sitemap", name)
	
	if sitemap.ref_doctype:
		generator = frappe.bean(sitemap.ref_doctype, sitemap.docname)
		if not generator.meta.has_field("parent_website_sitemap"):
			frappe.throw("Does not allow moving.")
		generator.doc.parent_website_sitemap = new_parent
		generator.save()
	else:
		frappe.msgprint("Template Pages cannot be moved.")
		
	clear_cache()
		