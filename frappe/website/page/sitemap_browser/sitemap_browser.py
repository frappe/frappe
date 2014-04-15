# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.website.render import clear_cache

@frappe.whitelist()
def get_children(parent=None):
	if not frappe.has_permission("Website Route"):
		raise frappe.PermissionError

	if parent=="Sitemap":
		parent = ""

	return frappe.db.sql("""select name as value, 1 as expandable, ref_doctype, docname
		from `tabWebsite Route` where
		ifnull(parent_website_route, '')=%s
			order by ifnull(idx,0), name asc""", parent, as_dict=True)

@frappe.whitelist()
def move(name, up_or_down):
	ret = None
	if not frappe.has_permission("Website Route"):
		raise frappe.PermissionError

	sitemap = frappe.get_doc("Website Route", name)
	if up_or_down=="up":
		if sitemap.idx > 0:
			prev = frappe.get_doc("Website Route", {
				"parent_website_route": sitemap.parent_website_route,
				"idx": sitemap.idx - 1
			})
			if prev.name:
				prev.idx = prev.idx + 1
				prev.save()

				sitemap.idx = sitemap.idx - 1
				sitemap.save()
				ret = "ok"

	else:
		nexts = frappe.get_doc("Website Route", {
			"parent_website_route": sitemap.parent_website_route,
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
	if not frappe.has_permission("Website Route"):
		raise frappe.PermissionError

	sitemap = frappe.get_doc("Website Route", name)

	if sitemap.ref_doctype:
		generator = frappe.get_doc(sitemap.ref_doctype, sitemap.docname)
		if not generator.meta.get_field("parent_website_route"):
			frappe.throw(_("Not allowed to move"))
		generator.parent_website_route = new_parent
		generator.save()
	else:
		frappe.msgprint(_("Template Pages cannot be moved"))

	clear_cache()
