<<<<<<< HEAD
from __future__ import unicode_literals
=======
>>>>>>> b2b391e90a (style: misc)
import frappe


def execute():
	frappe.flags.in_patch = True
	frappe.reload_doc("core", "doctype", "user_permission")
	frappe.db.commit()
