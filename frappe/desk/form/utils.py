# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from typing import TYPE_CHECKING

import frappe
import frappe.desk.form.load
import frappe.desk.form.meta
from frappe import _
from frappe.core.doctype.file.utils import extract_images_from_html
from frappe.desk.form.document_follow import follow_document

if TYPE_CHECKING:
	from frappe.core.doctype.comment.comment import Comment


@frappe.whitelist(methods=["DELETE", "POST"])
def remove_attach():
	"""remove attachment"""
	fid = frappe.form_dict.get("fid")
	frappe.delete_doc("File", fid)


@frappe.whitelist(methods=["POST", "PUT"])
def add_comment(
	reference_doctype: str, reference_name: str, content: str, comment_email: str, comment_by: str
) -> "Comment":
	"""Allow logged user with permission to read document to add a comment"""
	reference_doc = frappe.get_lazy_doc(reference_doctype, reference_name, check_permission=True)

	comment = frappe.new_doc("Comment")
	comment.update(
		{
			"comment_type": "Comment",
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"comment_email": comment_email,
			"comment_by": comment_by,
			"content": extract_images_from_html(reference_doc, content, is_private=True),
		}
	)
	comment.insert(ignore_permissions=True)

	if frappe.get_cached_value("User", frappe.session.user, "follow_commented_documents"):
		follow_document(comment.reference_doctype, comment.reference_name, frappe.session.user)

	return comment


@frappe.whitelist()
def update_comment(name, content):
	"""allow only owner to update comment"""
	doc = frappe.get_doc("Comment", name)

	if frappe.session.user not in ["Administrator", doc.owner]:
		frappe.throw(_("Comment can only be edited by the owner"), frappe.PermissionError)

	if doc.reference_doctype and doc.reference_name:
		reference_doc = frappe.get_lazy_doc(doc.reference_doctype, doc.reference_name, check_permission=True)

		doc.content = extract_images_from_html(reference_doc, content, is_private=True)
	else:
		doc.content = content

	doc.save(ignore_permissions=True)


@frappe.whitelist()
def update_comment_publicity(name: str, publish: bool):
	doc = frappe.get_doc("Comment", name)
	if frappe.session.user != doc.owner and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Comment publicity can only be updated by the original author or a System Manager."))

	doc.published = int(publish)
	doc.save(ignore_permissions=True)


@frappe.whitelist()
def get_next(
	doctype: str,
	value: str,
	prev: str | int,
	filters: dict | str | None = None,
	sort_order: str = "desc",
	sort_field: str = "creation",
):
	prev = int(prev)
	if not filters:
		filters = []
	if isinstance(filters, str):
		filters = json.loads(filters)

	table = frappe.qb.DocType(doctype)
	sort_column = table[sort_field]
	name_column = table.name
	current_sort_value = frappe.db.get_value(doctype, value, sort_field)

	is_ascending = sort_order.lower() == "asc"
	if prev == is_ascending:
		composite_condition = (sort_column < current_sort_value) | (
			(sort_column == current_sort_value) & (name_column < value)
		)
		order = frappe.qb.desc
	else:
		composite_condition = (sort_column > current_sort_value) | (
			(sort_column == current_sort_value) & (name_column > value)
		)
		order = frappe.qb.asc

	query = (
		frappe.qb.get_query(doctype, filters=filters, fields=["name"], ignore_permissions=False)
		.orderby(sort_column, order=order)
		.orderby(name_column, order=order)
		.where(composite_condition)
		.limit(1)
	)

	if res := query.run(as_list=True):
		return res[0][0]

	frappe.msgprint(_("No further records"))
	return None


def get_pdf_link(doctype, docname, print_format="Standard", no_letterhead=0):
	return f"/api/method/frappe.utils.print_format.download_pdf?doctype={doctype}&name={docname}&format={print_format}&no_letterhead={no_letterhead}"
