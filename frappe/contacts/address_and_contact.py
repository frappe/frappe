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
def remove_link(doctype: str, name: str, link_doctype: str, link_name: str) -> None:
	"""Remove the link between an Address or Contact and the document it is linked to."""
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
	"""Clear the document's primary Address/Contact field when it points at a record it no longer links to."""
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
	"""Document fields that hold its primary Address or Contact, by the same name convention the form uses."""
	return [
		df
		for df in meta.get("fields", {"fieldtype": "Link", "options": doctype})
		if "primary" in df.fieldname.lower()
	]


PARTY_DOCTYPES = ("Customer", "Supplier", "Company", "Sales Partner")


def get_party_links(doc) -> list[tuple[str, str]]:
	"""Party (Customer/Supplier/Company/Sales Partner) links stored on the `links` Dynamic Link child table."""
	return [
		(link.link_doctype, link.link_name)
		for link in doc.get("links") or []
		if link.link_doctype in PARTY_DOCTYPES
		and link.link_name
		# skip a stale link to a doctype whose app was uninstalled
		and frappe.db.exists("DocType", link.link_doctype, cache=True)
	]


def has_permission(doc, ptype, user):
	party_links = get_party_links(doc)
	if not party_links:
		# nothing to restrict by
		return True

	# permitted if the user has ptype permission on at least one linked party
	return any(
		frappe.has_permission(link_doctype, ptype, doc=link_name, user=user)
		for link_doctype, link_name in party_links
	)


def get_permission_query_conditions_for_contact(user):
	return get_permission_query_conditions("Contact", user)


def get_permission_query_conditions_for_address(user):
	return get_permission_query_conditions("Address", user)


def get_permission_query_conditions(doctype, user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return ""

	installed_party_doctypes = [d for d in PARTY_DOCTYPES if frappe.db.exists("DocType", d, cache=True)]
	if not installed_party_doctypes:
		# no app providing a party doctype is installed: nothing to restrict by
		return ""

	party_conditions = []
	for party_doctype in installed_party_doctypes:
		if not frappe.has_permission(party_doctype, "read", user=user):
			continue

		# get_list() applies every permission hook registered for this doctype
		permitted_names = frappe.get_list(party_doctype, pluck="name", user=user)
		if not permitted_names:
			continue

		escaped_names = ", ".join(frappe.db.escape(name) for name in permitted_names)
		party_conditions.append(
			f"""exists(
				select 1 from `tabDynamic Link` dl
				where dl.parent = `tab{doctype}`.name
					and dl.parenttype = {frappe.db.escape(doctype)}
					and dl.link_doctype = {frappe.db.escape(party_doctype)}
					and dl.link_name in ({escaped_names})
			)"""
		)

	no_party_condition = f"""not exists(
		select 1 from `tabDynamic Link` dl
		where dl.parent = `tab{doctype}`.name
			and dl.parenttype = {frappe.db.escape(doctype)}
			and dl.link_doctype in ({", ".join(frappe.db.escape(d) for d in installed_party_doctypes)})
	)"""

	return "(" + " or ".join([no_party_condition, *party_conditions]) + ")"


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
