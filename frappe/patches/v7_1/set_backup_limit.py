from __future__ import unicode_literals
from frappe.utils import cint
import frappe

def execute():
    backup_limit = frappe.db.get_single_value('System Settings', 'backup_limit')
    
    if cint(backup_limit) == 0:
        frappe.db.set_value('System Settings', 'System Settings', 'backup_limit', 3)
