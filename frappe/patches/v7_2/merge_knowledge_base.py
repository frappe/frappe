from __future__ import unicode_literals
import frappe

from frappe.patches.v7_0.re_route import update_routes
from frappe.installer import remove_from_installed_apps

def execute():
	if 'knowledge_base' in frappe.get_installed_apps():
		frappe.reload_doc('website', 'doctype', 'help_category')
		frappe.reload_doc('website', 'doctype', 'help_article')
		update_routes(['Help Category', 'Help Article'])
		remove_from_installed_apps('knowledge_base')

		# remove module def
		if frappe.db.exists('Module Def', 'Knowledge Base'):
			frappe.delete_doc('Module Def', 'Knowledge Base')

		# set missing routes
		for doctype in ('Help Category', 'Help Article'):
			for d in frappe.get_all(doctype, fields=['name', 'route']):
				if not d.route:
					doc = frappe.get_doc(doctype, d.name)
					doc.set_route()
					doc.db_update()