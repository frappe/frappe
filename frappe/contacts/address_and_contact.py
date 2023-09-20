# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import functools
import re

import frappe
from frappe import _


def load_address_and_contact(doc, key=None):
	"""Loads address list and contact list in `__onload`"""
	from frappe.contacts.doctype.address.address import get_address_display, get_condensed_address

	filters = [
		["Dynamic Link", "link_doctype", "=", doc.doctype],
		["Dynamic Link", "link_name", "=", doc.name],
		["Dynamic Link", "parenttype", "=", "Address"],
	]
	address_list = frappe.get_list("Address", filters=filters, fields=["*"], order_by="creation asc")

	address_list = [a.update({"display": get_address_display(a)}) for a in address_list]

	address_list = sorted(
		address_list,
		key=functools.cmp_to_key(
			lambda a, b: (int(a.is_primary_address - b.is_primary_address))
			or (1 if a.modified - b.modified else 0)
		),
		reverse=True,
	)

	doc.set_onload("addr_list", address_list)

	contact_list = []
	filters = [
		["Dynamic Link", "link_doctype", "=", doc.doctype],
		["Dynamic Link", "link_name", "=", doc.name],
		["Dynamic Link", "parenttype", "=", "Contact"],
	]
	contact_list = frappe.get_list("Contact", filters=filters, fields=["*"])

	for contact in contact_list:
		contact["email_ids"] = frappe.get_all(
			"Contact Email",
			filters={"parenttype": "Contact", "parent": contact.name, "is_primary": 0},
			fields=["email_id"],
		)

		contact["phone_nos"] = frappe.get_all(
			"Contact Phone",
			filters={
				"parenttype": "Contact",
				"parent": contact.name,
				"is_primary_phone": 0,
				"is_primary_mobile_no": 0,
			},
			fields=["phone"],
		)

		if contact.address:
			address = frappe.get_doc("Address", contact.address)
			contact["address"] = get_condensed_address(address)

	contact_list = sorted(
		contact_list,
		key=functools.cmp_to_key(
			lambda a, b: (int(a.is_primary_contact - b.is_primary_contact))
			or (1 if a.modified - b.modified else 0)
		),
		reverse=True,
	)

	doc.set_onload("contact_list", contact_list)


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
		conditions = []

		# when everything is not permitted
		for df in links.get("not_permitted_links"):
			# like ifnull(customer, '')='' and ifnull(supplier, '')=''
			conditions.append(f"ifnull(`tab{doctype}`.`{df.fieldname}`, '')=''")

		return "( " + " and ".join(conditions) + " )"

	else:
		conditions = []

		for df in links.get("permitted_links"):
			# like ifnull(customer, '')!='' or ifnull(supplier, '')!=''
			conditions.append(f"ifnull(`tab{doctype}`.`{df.fieldname}`, '')!=''")

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
	doctype, txt: str, searchfield, start, page_len, filters: dict
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
		if not link.link_title:
			linked_doc = frappe.get_doc(link.link_doctype, link.link_name)
			link.link_title = linked_doc.get_title() or link.link_name
