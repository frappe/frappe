# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from typing import Any

import frappe
from frappe import _


def load_address_and_contact(doc, key=None) -> None:
	"""Loads address list and contact list in `__onload`"""
	from frappe.contacts.doctype.address.address import get_address_display_list
	from frappe.contacts.doctype.contact.contact import get_contact_display_list

	doc.set_onload("addr_list", get_address_display_list(doc.doctype, doc.name))
	doc.set_onload("contact_list", get_contact_display_list(doc.doctype, doc.name))


@frappe.whitelist()
def delink_party(doctype: str, name: str, link_doctype: str, link_name: str) -> None:
	"""Remove the link between an Address or Contact and the given party."""
	if doctype not in ("Address", "Contact"):
		frappe.throw(_("Can only unlink an Address or a Contact"))

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")

	remaining = [
		link for link in doc.links if not (link.link_doctype == link_doctype and link.link_name == link_name)
	]
	if len(remaining) == len(doc.links):
		return

	doc.links = remaining
	doc.save()

	clear_stale_primary_link(doctype, name, link_doctype, link_name)


def clear_stale_primary_link(doctype: str, name: str, link_doctype: str, link_name: str) -> None:
	"""Clear the party's primary Address/Contact field when it points at a record it no longer links to."""
	meta = frappe.get_meta(link_doctype)
	primary_fields = [df.fieldname for df in get_primary_link_fields(meta, doctype)]
	if not primary_fields:
		return

	values = frappe.db.get_value(link_doctype, link_name, primary_fields, as_dict=True) or {}
	stale_fields = [fieldname for fieldname in primary_fields if values.get(fieldname) == name]
	if not stale_fields:
		return

	frappe.has_permission(link_doctype, "write", doc=link_name, throw=True)

	updates = dict.fromkeys(stale_fields)
	for df in meta.fields:
		if df.fetch_from and df.fetch_from.split(".")[0] in stale_fields:
			updates[df.fieldname] = None

	frappe.db.set_value(link_doctype, link_name, updates)


def get_primary_link_fields(meta, doctype: str) -> list:
	"""Party fields that hold its primary Address or Contact, by the same name convention the form uses."""
	return [
		df
		for df in meta.get("fields", {"fieldtype": "Link", "options": doctype})
		if "primary" in df.fieldname.lower()
	]


def has_permission(doc, ptype, user):
	links = get_permitted_and_not_permitted_links(doc.doctype)
	if not links.get("not_permitted_links"):
		# optimization: don't determine permissions based on link fields
		return True

	# True if any one is True or all are empty
	names = []
	for df in links.get("permitted_links") + links.get("not_permitted_links"):
		doctype = df.options
		name = doc.get(df.fieldname)
		names.append(name)

		if name and frappe.has_permission(doctype, ptype, doc=name):
			return True

	if not any(names):
		return True
	return False


def get_permission_query_conditions_for_contact(user):
	return get_permission_query_conditions("Contact")


def get_permission_query_conditions_for_address(user):
	return get_permission_query_conditions("Address")


def get_permission_query_conditions(doctype):
	links = get_permitted_and_not_permitted_links(doctype)

	if not links.get("not_permitted_links"):
		# when everything is permitted, don't add additional condition
		return ""

	elif not links.get("permitted_links"):
		# when everything is not permitted
		conditions = [
			f"ifnull(`tab{doctype}`.`{df.fieldname}`, '')=''" for df in links.get("not_permitted_links")
		]

		return "( " + " and ".join(conditions) + " )"

	else:
		conditions = [
			f"ifnull(`tab{doctype}`.`{df.fieldname}`, '')!=''" for df in links.get("permitted_links")
		]

		return "( " + " or ".join(conditions) + " )"


def get_permitted_and_not_permitted_links(doctype):
	permitted_links = []
	not_permitted_links = []

	meta = frappe.get_meta(doctype)
	allowed_doctypes = frappe.permissions.get_doctypes_with_read()

	for df in meta.get_link_fields():
		if df.options not in ("Customer", "Supplier", "Company", "Sales Partner"):
			continue

		if df.options in allowed_doctypes:
			permitted_links.append(df)
		else:
			not_permitted_links.append(df)

	return {"permitted_links": permitted_links, "not_permitted_links": not_permitted_links}


def delete_contact_and_address(doctype: str, docname: str) -> None:
	for parenttype in ("Contact", "Address"):
		for name in frappe.get_all(
			"Dynamic Link",
			filters={
				"parenttype": parenttype,
				"link_doctype": doctype,
				"link_name": docname,
			},
			pluck="parent",
		):
			doc = frappe.get_doc(parenttype, name)
			if len(doc.links) == 1:
				doc.delete()
			else:
				for link in doc.links:
					if link.link_doctype == doctype and link.link_name == docname:
						doc.remove(link)
						doc.save()
						break


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def filter_dynamic_link_doctypes(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: dict[str, Any]
) -> list[list[str]]:
	from frappe.permissions import get_doctypes_with_read

	txt = txt or ""
	filters = filters or {}

	_doctypes_from_df = frappe.get_all(
		"DocField",
		filters=filters,
		pluck="parent",
		distinct=True,
		order_by=None,
	)
	doctypes_from_df = {d for d in _doctypes_from_df if txt.lower() in _(d).lower()}

	filters.update({"dt": ("not in", doctypes_from_df)})
	_doctypes_from_cdf = frappe.get_all(
		"Custom Field", filters=filters, pluck="dt", distinct=True, order_by=None
	)
	doctypes_from_cdf = {d for d in _doctypes_from_cdf if txt.lower() in _(d).lower()}

	all_doctypes = doctypes_from_df.union(doctypes_from_cdf)
	allowed_doctypes = set(get_doctypes_with_read())

	valid_doctypes = sorted(all_doctypes.intersection(allowed_doctypes))

	return [[doctype] for doctype in valid_doctypes]


def set_link_title(doc):
	if not doc.links:
		return
	for link in doc.links:
		linked_doc = frappe.get_doc(link.link_doctype, link.link_name)
		doc_title = linked_doc.get_title()
		if link.link_title != doc_title:
			link.link_title = doc_title or link.link_name
