# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def sendmail_to_system_managers(subject, content):
	frappe.sendmail(recipients=get_system_managers(), subject=subject, content=content)

@frappe.whitelist()
def get_contact_list(doctype, fieldname, txt):
	"""Returns contacts (from autosuggest)"""
	txt = txt.replace('%', '')

	def get_users():
		return filter(None, frappe.db.sql_list('select email from tabUser where email like %s',
			('%' + txt + '%')))
	try:
		out = filter(None, frappe.db.sql_list('select `{0}` from `tab{1}` where `{0}` like %s'.format(fieldname, doctype),
			'%' + txt + '%'))
		if out:
			out = get_users()
	except Exception, e:
		if e.args[0]==1146:
			# no Contact, use User
			out = get_users()
		else:
			raise

	return out

def get_system_managers():
	return frappe.db.sql_list("""select parent FROM tabUserRole
		WHERE role='System Manager'
		AND parent!='Administrator'
		AND parent IN (SELECT email FROM tabUser WHERE enabled=1)""")
