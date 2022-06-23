# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import json

from six import string_types

import frappe
import frappe.desk.form.load
import frappe.desk.form.meta
from frappe import _
from frappe.core.doctype.file.file import extract_images_from_html
from frappe.desk.form.document_follow import follow_document


@frappe.whitelist()
def remove_attach():
	"""remove attachment"""
	fid = frappe.form_dict.get("fid")
	file_name = frappe.form_dict.get("file_name")
	frappe.delete_doc("File", fid)


@frappe.whitelist()
def add_comment(reference_doctype, reference_name, content, comment_email, comment_by):
	"""allow any logged user to post a comment"""
	doc = frappe.get_doc(
		dict(
			doctype="Comment",
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			comment_email=comment_email,
			comment_type="Comment",
			comment_by=comment_by,
		)
	)
	reference_doc = frappe.get_doc(reference_doctype, reference_name)
	doc.content = extract_images_from_html(reference_doc, content, is_private=True)
	doc.insert(ignore_permissions=True)

	follow_document(doc.reference_doctype, doc.reference_name, frappe.session.user)
	return doc.as_dict()


@frappe.whitelist()
def update_comment(name, content):
	"""allow only owner to update comment"""
	doc = frappe.get_doc("Comment", name)

	if frappe.session.user not in ["Administrator", doc.owner]:
		frappe.throw(_("Comment can only be edited by the owner"), frappe.PermissionError)

	doc.content = content
	doc.save(ignore_permissions=True)


@frappe.whitelist()
def get_next(doctype, value, prev, filters=None, sort_order="desc", sort_field="modified"):

	prev = int(prev)
	if not filters:
		filters = []
	if isinstance(filters, string_types):
		filters = json.loads(filters)

	# # condition based on sort order
	condition = ">" if sort_order.lower() == "asc" else "<"

	# switch the condition
	if prev:
		sort_order = "asc" if sort_order.lower() == "desc" else "desc"
		condition = "<" if condition == ">" else ">"

	# # add condition for next or prev item
	filters.append([doctype, sort_field, condition, frappe.get_value(doctype, value, sort_field)])

	res = frappe.get_list(
		doctype,
		fields=["name"],
		filters=filters,
		order_by="`tab{0}`.{1}".format(doctype, sort_field) + " " + sort_order,
		limit_start=0,
		limit_page_length=1,
		as_list=True,
	)

	if not res:
		frappe.msgprint(_("No further records"))
		return None
	else:
		return res[0][0]


def get_pdf_link(doctype, docname, print_format="Standard", no_letterhead=0):
	return "/api/method/frappe.utils.print_format.download_pdf?doctype={doctype}&name={docname}&format={print_format}&no_letterhead={no_letterhead}".format(
		doctype=doctype, docname=docname, print_format=print_format, no_letterhead=no_letterhead
	)
