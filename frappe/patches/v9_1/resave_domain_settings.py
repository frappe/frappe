from __future__ import unicode_literals
import frappe

def execute():
	domain_settings = frappe.get_doc('Domain Settings')
	active_domains = [d.domain for d in domain_settings.active_domains]
	try:
		for d in ('Education', 'Healthcare', 'Hospitality'):
			if d in active_domains and frappe.db.exists('Domain', d):
				domain = frappe.get_doc('Domain', d)
				domain.setup_domain()
	except frappe.LinkValidationError:
		pass
