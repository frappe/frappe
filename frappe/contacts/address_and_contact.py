# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe import _
import functools
import re

def load_address_and_contact(doc, key=None):
	"""Loads address list and contact list in `__onload`"""
	from frappe.contacts.doctype.address.address import get_address_display, get_condensed_address

	filters = [
		["Dynamic Link", "link_doctype", "=", doc.doctype],
		["Dynamic Link", "link_name", "=", doc.name],
		["Dynamic Link", "parenttype", "=", "Address"],
	]
	address_list = frappe.get_all("Address", filters=filters, fields=["*"])

	address_list = [a.update({"display": get_address_display(a)})
		for a in address_list]

	address_list = sorted(address_list,
		key = functools.cmp_to_key(lambda a, b:
			(int(a.is_primary_address - b.is_primary_address)) or
			(1 if a.modified - b.modified else 0)), reverse=True)

	doc.set_onload('addr_list', address_list)

	contact_list = []
	filters = [
		["Dynamic Link", "link_doctype", "=", doc.doctype],
		["Dynamic Link", "link_name", "=", doc.name],
		["Dynamic Link", "parenttype", "=", "Contact"],
	]
	contact_list = frappe.get_all("Contact", filters=filters, fields=["*"])

	for contact in contact_list:
		contact["email_ids"] = frappe.get_list("Contact Email", filters={
				"parenttype": "Contact",
				"parent": contact.name,
				"is_primary": 0
			}, fields=["email_id"])

		contact["phone_nos"] = frappe.get_list("Contact Phone", filters={
				"parenttype": "Contact",
				"parent": contact.name,
				"is_primary_phone": 0,
				"is_primary_mobile_no": 0
			}, fields=["phone"])

		if contact.address:
			address = frappe.get_doc("Address", contact.address)
			contact["address"] = get_condensed_address(address)

	contact_list = sorted(contact_list,
		key = functools.cmp_to_key(lambda a, b:
			(int(a.is_primary_contact - b.is_primary_contact)) or
			(1 if a.modified - b.modified else 0)), reverse=True)

	doc.set_onload('contact_list', contact_list)

def has_permission(doc, ptype, user):
	links = get_permitted_and_not_permitted_links(doc.doctype)
	if not links.get("not_permitted_links"):
		# optimization: don't determine permissions based on link fields
		return True

	# True if any one is True or all are empty
	names = []
	for df in (links.get("permitted_links") + links.get("not_permitted_links")):
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
			conditions.append("ifnull(`tab{doctype}`.`{fieldname}`, '')=''".format(doctype=doctype, fieldname=df.fieldname))

		return "( " + " and ".join(conditions) + " )"

	else:
		conditions = []

		for df in links.get("permitted_links"):
			# like ifnull(customer, '')!='' or ifnull(supplier, '')!=''
			conditions.append("ifnull(`tab{doctype}`.`{fieldname}`, '')!=''".format(doctype=doctype, fieldname=df.fieldname))

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

	return {
		"permitted_links": permitted_links,
		"not_permitted_links": not_permitted_links
	}

def delete_contact_and_address(doctype, docname):
	for parenttype in ('Contact', 'Address'):
		items = frappe.db.sql_list("""select parent from `tabDynamic Link`
			where parenttype=%s and link_doctype=%s and link_name=%s""",
			(parenttype, doctype, docname))

		for name in items:
			doc = frappe.get_doc(parenttype, name)
			if len(doc.links)==1:
				doc.delete()

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def filter_dynamic_link_doctypes(doctype, txt, searchfield, start, page_len, filters):
	if not txt: txt = ""

	doctypes = frappe.db.get_all("DocField", filters=filters, fields=["parent"],
		distinct=True, as_list=True)

	doctypes = tuple([d for d in doctypes if re.search(txt+".*", _(d[0]), re.IGNORECASE)])

	filters.update({
		"dt": ("not in", [d[0] for d in doctypes])
	})

	_doctypes = frappe.db.get_all("Custom Field", filters=filters, fields=["dt"],
		as_list=True)

	_doctypes = tuple([d for d in _doctypes if re.search(txt+".*", _(d[0]), re.IGNORECASE)])

	all_doctypes = [d[0] for d in doctypes + _doctypes]
	allowed_doctypes = frappe.permissions.get_doctypes_with_read()

	valid_doctypes = sorted(set(all_doctypes).intersection(set(allowed_doctypes)))
	valid_doctypes = [[doctype] for doctype in valid_doctypes]

	return valid_doctypes

def set_link_title(doc):
	if not doc.links:
		return
	for link in doc.links:
		if not link.link_title:
			linked_doc = frappe.get_doc(link.link_doctype, link.link_name)
			link.link_title = linked_doc.get("title_field") or linked_doc.get("name")
