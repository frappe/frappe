# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.website.website_generator import WebsiteGenerator

# parameters
# name (edit)
# new

class WebForm(WebsiteGenerator):
	template = "templates/generators/web_form.html"
	condition_field = "published"
	page_title_field = "title"
	no_cache = 1

	def get_context(self, context):
		context.params = frappe.form_dict
		if frappe.form_dict.name:
			context.doc = frappe.get_doc(self.doc_type, frappe.form_dict.name)

		return context

@frappe.whitelist(allow_guest=True)
def accept():
	args = frappe.form_dict
	if args.name:
		doc = frappe.get_doc(args.doctype, args.name)
	else:
		doc = frappe.new_doc(args.doctype)

	for fieldname, value in args.iteritems():
		if fieldname not in ("web_form", "cmd"):
			doc.set(fieldname, value)

	if args.name:
		if doc.owner==frappe.session.user:
			doc.update(ignore_permissions=True)
		else:
			# only if permissions are present
			doc.update()

	else:
		# insert
		web_form = frappe.get_doc("Web Form", args.web_form)
		if web_form.login_required and frappe.session.user=="Guest":
			frappe.throw(_("You must login to submit this form"))

		doc.insert(ignore_permissions = True)
