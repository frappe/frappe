from __future__ import unicode_literals
import frappe
from frappe.permissions import reset_perms

def execute():
	frappe.reload_doctype("Communication")

	# set status = "Linked"
	frappe.db.sql("""update `tabCommunication` set status='Linked'
		where ifnull(reference_doctype, '')!='' and ifnull(reference_name, '')!=''""")

	frappe.db.sql("""update `tabCommunication` set status='Closed'
		where status='Archived'""")

	# reset permissions if owner of all DocPerms is Administrator
	if not frappe.db.sql("""select name from `tabDocPerm`
		where parent='Communication' and ifnull(owner, '')!='Administrator'"""):

		reset_perms("Communication")
