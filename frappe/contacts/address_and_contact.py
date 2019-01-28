# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe import _
import functools
import re

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
	valid_doctypes = []

	for doctype in all_doctypes:
		if frappe.has_permission(doctype):
			valid_doctypes.append([doctype])

	return sorted(valid_doctypes)

# ADDRESS #
@frappe.whitelist()
def check_address_email_phone_fax_already_exist(email_id="", phone="", fax="", name=""):
	'''Check when save an address if the email, phone number or fax is already registered in another address'''
	email_id = email_id.strip()
	phone = phone.strip()
	fax = fax.strip()
	name = name.strip()

	email_id_address = check_address_email_already_exist(email_id, name)
	phone_address = check_address_phone_number_already_exist(phone, name)
	fax_address = check_address_fax_already_exist(fax, name)

	# for cross checking on contact
	email_id_contact = check_contact_email_already_exist(email_id, name)
	phone_contact = check_contact_phone_number_already_exist(phone, name)
	mobile_no_contact = check_contact_mobile_number_already_exist(fax, name)

	return_addresses = email_id_address + email_id_contact + phone_address + phone_contact + fax_address + mobile_no_contact

	if return_addresses != "":
		return_addresses = return_addresses[:-1]

	return return_addresses

def check_address_email_already_exist(email_id="", name=""):
	m_return = ""
	if email_id != "":
		addresses = frappe.db.sql("""select name from `tabAddress` where trim(email_id) = %s
			and name <> %s""", (email_id, name), as_dict=True)
		for address in addresses:
			m_return += "Email ID/Email ID" + ":" + address.name + ";Address" + ","

	return m_return

def check_address_phone_number_already_exist(phone="", name=""):
	m_return = ""
	if phone != "":
		addresses_phone = frappe.db.sql("""select name from `tabAddress` where replace(trim(phone), ' ', '') = %s and name <> %s""",
		                          (phone.replace(" ", ""), name), as_dict=True)
		for address_phone in addresses_phone:
			m_return += "Phone/Phone" + ":" + address_phone.name + ";Address" + ","

		addresses_fax = frappe.db.sql("""select name from `tabAddress` where replace(trim(fax), ' ', '') = %s and name <> %s""",
		                          (phone.replace(" ", ""), name), as_dict=True)
		for address_fax in addresses_fax:
			m_return += "Phone/Fax" + ":" + address_fax.name + ";Address" + ","

	return m_return

def check_address_fax_already_exist(fax="", name=""):
	m_return = ""
	if fax != "":
		addresses_fax = frappe.db.sql("""select name from `tabAddress` where replace(trim(fax), ' ', '') = %s and name <> %s""",
		                          (fax.replace(" ", ""), name), as_dict=True)
		for address_fax in addresses_fax:
			m_return += "Fax/Fax" + ":" + address_fax.name + ";Address" + ","

		addresses_phone = frappe.db.sql("""select name from `tabAddress` where replace(trim(phone), ' ', '') = %s and name <> %s""",
		                          (fax.replace(" ", ""), name), as_dict=True)
		for address_phone in addresses_phone:
			m_return += "Fax/Phone" + ":" + address_phone.name + ";Address" + ","

	return m_return

# CONTACT #
@frappe.whitelist()
def check_contact_email_phone_mobile_number_already_exist(email_id="", phone="", mobile_no="", name=""):
	'''Check when save a contact if the email, phone number or mobile number is already registered in another contact'''
	email_id = email_id.strip()
	phone = phone.strip()
	mobile_no = mobile_no.strip()
	name = name.strip()

	email_id_contact = check_contact_email_already_exist(email_id, name)
	phone_contact = check_contact_phone_number_already_exist(phone, name)
	mobile_no_contact = check_contact_mobile_number_already_exist(mobile_no, name)

	# for cross checking on address
	email_id_address = check_address_email_already_exist(email_id, name)
	phone_address = check_address_phone_number_already_exist(phone, name)
	fax_address = check_address_fax_already_exist(mobile_no, name)

	return_contacts = email_id_contact + email_id_address + phone_contact + phone_address + mobile_no_contact + fax_address

	if return_contacts != "":
		return_contacts = return_contacts[:-1]

	return return_contacts

def check_contact_email_already_exist(email_id="", name=""):
	m_return = ""
	if email_id != "":
		contacts = frappe.db.sql("""select name from `tabContact` where trim(email_id) = %s and
			name <> %s""", (email_id, name), as_dict=True)
		for contact in contacts:
			m_return += "Email ID/Email ID" + ":" + contact.name + ";Contact" + ","

	return m_return

def check_contact_phone_number_already_exist(phone="", name=""):
	m_return = ""
	if phone != "":
		contacts_phone = frappe.db.sql("""select name from `tabContact` where replace(trim(phone), ' ', '') = %s and name <> %s""",
		                         (phone.replace(" ", ""), name), as_dict=True)
		for contact_phone in contacts_phone:
			m_return += "Phone/Phone" + ":" + contact_phone.name + ";Contact" + ","

		contacts_mobile_no = frappe.db.sql("""select name from `tabContact` where replace(trim(mobile_no), ' ', '') = %s and name <> %s""",
		                         (phone.replace(" ", ""), name), as_dict=True)
		for contact_mobile_no in contacts_mobile_no:
			m_return += "Phone/Mobile Number" + ":" + contact_mobile_no.name + ";Contact" + ","

	return m_return

def check_contact_mobile_number_already_exist(mobile_no="", name=""):
	m_return = ""
	if mobile_no != "":
		contacts_mobile_no = frappe.db.sql("""select name from `tabContact` where replace(trim(mobile_no), ' ', '') = %s and name <> %s""",
		                         (mobile_no.replace(" ", ""), name), as_dict=True)
		for contact_mobile_no in contacts_mobile_no:
			m_return += "Mobile Number/Mobile Number" + ":" + contact_mobile_no.name + ";Contact" + ","

		contacts_phone = frappe.db.sql("""select name from `tabContact` where replace(trim(phone), ' ', '') = %s and name <> %s""",
		                         (mobile_no.replace(" ", ""), name), as_dict=True)
		for contact_phone in contacts_phone:
			m_return += "Mobile Number/Phone" + ":" + contact_phone.name + ";Contact" + ","

	return m_return
