# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def sendmail_to_system_managers(subject, content):
	frappe.sendmail(recipients=get_system_managers(), subject=subject, content=content)

@frappe.whitelist()
def get_contact_list():
	"""Returns contacts (from autosuggest)"""

	try:
		out = frappe.db.sql("""select email_id, first_name, last_name from `tabContact`""")
		out = filter(None, out)

	except Exception as e:
		raise

	return out

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

def get_communication_doctype(doctype, txt, searchfield, start, page_len, filters):
	user_perms = frappe.utils.user.UserPermissions(frappe.session.user)
	user_perms.build_permissions()
	can_read = user_perms.can_read
	from frappe.modules import load_doctype_module
	com_doctypes = []
	if len(txt)<2:

		for name in ["Customer", "Supplier"]:
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


