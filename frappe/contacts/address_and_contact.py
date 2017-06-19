# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def load_address_and_contact(doc, key=None):
	"""Loads address list and contact list in `__onload`"""
	from frappe.contacts.doctype.address.address import get_address_display

	filters = [
		["Dynamic Link", "link_doctype", "=", doc.doctype],
		["Dynamic Link", "link_name", "=", doc.name],
		["Dynamic Link", "parenttype", "=", "Address"],
	]
	address_list = frappe.get_all("Address", filters=filters, fields=["*"])

	address_list = [a.update({"display": get_address_display(a)})
		for a in address_list]

	address_list = sorted(address_list,
		lambda a, b:
			(int(a.is_primary_address - b.is_primary_address)) or
			(1 if a.modified - b.modified else 0), reverse=True)

	doc.set_onload('addr_list', address_list)

	contact_list = []
	if doc.doctype != "Lead":
		filters = [
			["Dynamic Link", "link_doctype", "=", doc.doctype],
			["Dynamic Link", "link_name", "=", doc.name],
			["Dynamic Link", "parenttype", "=", "Contact"],
		]
		contact_list = frappe.get_all("Contact", filters=filters, fields=["*"])

		contact_list = sorted(contact_list,
			lambda a, b:
				(int(a.is_primary_contact - b.is_primary_contact)) or
				(1 if a.modified - b.modified else 0), reverse=True)

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

	for df in meta.get_link_fields():
		if df.options not in ("Customer", "Supplier", "Company", "Sales Partner"):
			continue

		if frappe.has_permission(df.options):
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

def filter_dynamic_link_doctypes(doctype, txt, searchfield, start, page_len, filters):
	if not txt: txt = ""

	txt = txt.lower()
	txt = "%%%s%%" % (txt)

	filters.update({
		"parent": ("like", txt)
	})

	doctypes = frappe.db.get_all("DocField", filters=filters, fields=["parent"],
		order_by="parent asc", distinct=True, as_list=True)

	filters.pop("parent")
	filters.update({
		"dt": ("not in", [d[0] for d in doctypes]),
		"dt": ("like", txt),
	})

	_doctypes = frappe.db.get_all("Custom Field", filters=filters, fields=["dt"],
		order_by="dt asc", as_list=True)

	all_doctypes = doctypes + _doctypes
	return sorted(all_doctypes, key=lambda item: item[0])