from __future__ import unicode_literals
import frappe
from frappe.permissions import setup_custom_perms
from frappe.core.page.permission_manager.permission_manager import get_standard_permissions
from frappe.utils.reset_doc import setup_perms_for

'''
Copy DocPerm to Custom DocPerm where permissions are set differently
'''

def execute():
	for d in frappe.db.get_all('DocType', dict(istable=0, issingle=0, custom=0)):
		setup_perms_for(d.name)
