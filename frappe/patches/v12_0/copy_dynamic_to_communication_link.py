from __future__ import unicode_literals

import frappe

def execute():
	frappe.db.sql("""
		INSERT INTO `tabCommunication Link`
		SELECT * FROM `tabDynamic Link`
		WHERE `tabDynamic Link`.parenttype='Communication'
	""")

	frappe.db.sql("""
		DELETE FROM `tabDynamic Link`
		WHERE `tabDynamic Link`.parenttype='Communication'
	""")

	frappe.db.add_index("Communication Link", ["link_doctype", "link_name"])