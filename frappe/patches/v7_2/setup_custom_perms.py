import frappe
from frappe.permissions import setup_custom_perms
from frappe.core.page.permission_manager.permission_manager import get_standard_permissions

'''
Copy DocPerm to Custom DocPerm where permissions are set differently
'''

def execute():
	for d in frappe.db.get_all('DocType', dict(istable=0, issingle=0, custom=0)):
		setup_perms_for(d.name)

def setup_perms_for(doctype):
	perms = frappe.get_all('DocPerm', fields='*', filters=dict(parent=doctype), order_by='idx asc')
	# get default perms
	try:
		standard_perms = get_standard_permissions(doctype)
	except (IOError, KeyError):
		# no json file, doctype no longer exists!
		return

	same = True
	if len(standard_perms) != len(perms):
		same = False

	else:
		for i, p in enumerate(perms):
			standard = standard_perms[i]
			for fieldname in frappe.get_meta('DocPerm').get_fieldnames_with_value():
				if p.get(fieldname) != standard.get(fieldname):
					same = False
					break

			if not same:
				break

	if not same:
		setup_custom_perms(doctype)
