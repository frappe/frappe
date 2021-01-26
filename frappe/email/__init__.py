# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.desk.reportview import build_match_conditions

def sendmail_to_system_managers(subject, content):
	frappe.sendmail(recipients=get_system_managers(), subject=subject, content=content)

@frappe.whitelist()
def get_contact_list(txt, page_length=20):
	"""Returns contacts (from autosuggest)"""

	cached_contacts = get_cached_contacts(txt)
	if cached_contacts:
		return clean_duplicates(cached_contacts[:page_length])

	try:
		match_conditions_contact = build_match_conditions('Contact')
		match_conditions_address = build_match_conditions('Address')

		out = frappe.db.sql("""
			SELECT
				email_id AS value,
				CONCAT(first_name, IFNULL(CONCAT(' ',last_name), '' )) AS description
			FROM tabContact
			WHERE
				name LIKE %(txt)s
				OR email_id LIKE %(txt)s
				%(cond_contact)s
			UNION SELECT
				email_id AS value,
				name AS description
			FROM tabAddress
			WHERE
				name LIKE %(txt)s
				OR email_id LIKE %(txt)s
				%(cond_address)s		
			LIMIT %(page_length)s""", {
				'txt': '%' + txt + '%',
				'cond_contact': "AND {0}".format(match_conditions_contact) if match_conditions_contact else "",
				'cond_address': "AND {0}".format(match_conditions_address) if match_conditions_address else "",
				'page_length': page_length
		}, as_dict=True)
		#out = filter(None, out)

	except:
		raise

	update_contact_cache(out)

	return clean_duplicates(out)

def get_system_managers():
	return frappe.db.sql_list("""select parent FROM `tabHas Role`
		WHERE role='System Manager'
		AND parent!='Administrator'
		AND parent IN (SELECT email FROM tabUser WHERE enabled=1)""")

@frappe.whitelist()
def relink(name, reference_doctype=None, reference_name=None):
	frappe.db.sql("""update
			`tabCommunication`
		set
			reference_doctype = %s,
			reference_name = %s,
			status = "Linked"
		where
			communication_type = "Communication" and
			name = %s""", (reference_doctype, reference_name, name))

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_communication_doctype(doctype, txt, searchfield, start, page_len, filters):
	user_perms = frappe.utils.user.UserPermissions(frappe.session.user)
	user_perms.build_permissions()
	can_read = user_perms.can_read
	from frappe.modules import load_doctype_module
	com_doctypes = []
	if len(txt)<2:

		for name in frappe.get_hooks("communication_doctypes"):
			try:
				module = load_doctype_module(name, suffix='_dashboard')
				if hasattr(module, 'get_data'):
					for i in module.get_data()['transactions']:
						com_doctypes += i["items"]
			except ImportError:
				pass
	else:
		com_doctypes = [d[0] for d in frappe.db.get_values("DocType", {"issingle": 0, "istable": 0, "hide_toolbar": 0})]

	out = []
	for dt in com_doctypes:
		if txt.lower().replace("%", "") in dt.lower() and dt in can_read:
			out.append([dt])
	return out

def get_cached_contacts(txt):
	contacts = frappe.cache().hget("contacts", frappe.session.user) or []

	if not contacts:
		return

	if not txt:
		return contacts

	match = [d for d in contacts if (d.value and (
		(d.value and txt.lower() in d.value.lower()) or \
		(d.description and txt.lower() in d.description.lower())
		))]
	return match

def update_contact_cache(contacts):
	cached_contacts = frappe.cache().hget("contacts", frappe.session.user) or []

	uncached_contacts = [d for d in contacts if d not in cached_contacts]
	cached_contacts.extend(uncached_contacts)

	frappe.cache().hset("contacts", frappe.session.user, cached_contacts)

def clean_duplicates(contacts):
	result = {}
	for contact in contacts:
		result[contact.value] = contact
	
	return result.values()
