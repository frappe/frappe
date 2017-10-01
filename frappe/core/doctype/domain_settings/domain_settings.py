# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.model.document import Document

class DomainSettings(Document):
	def on_update(self):
		clear_domain_cache()

def get_active_domains():
	""" get the domains set in the Domain Settings as active domain """
	def _get_active_domains():
		domains = frappe.get_all("Has Domain", filters={ "parent": "Domain Settings" },
			fields=["domain"], distinct=True)

		active_domains = [row.get("domain") for row in domains]
		active_domains.append("")
		return active_domains

	return frappe.cache().get_value("active_domains", _get_active_domains)

def get_active_modules():
	""" get the active modules from Module Def"""
	def _get_active_modules():
		active_modules = []
		active_domains = get_active_domains()
		for m in frappe.get_all("Module Def", fields=['name', 'restrict_to_domain']):
			if (not m.restrict_to_domain) or (m.restrict_to_domain in active_domains):
				active_modules.append(m.name)
		return active_modules

	return frappe.cache().get_value('active_modules', _get_active_modules)

def clear_domain_cache():
	frappe.cache().delete_key(['active_domains', 'active_modules'])

@frappe.whitelist()
def set_roles(active_domains):
	active_domains = json.loads(active_domains)
	user = frappe.get_doc("User", frappe.session.user)
	for domain in active_domains:
		roles = get_domain(domain)
		if roles:
			[(frappe.set_value('Role', role, 'disabled', 0)) for role in roles.allow_roles]
			user.add_roles(*roles.allow_roles)

def get_domain(domain):
		data = {
			'Healthcare': {
				'allow_roles': ['Physician', 'Nursing User', 'Laboratory user', 
					'LabTest Approver', 'Healthcare Administrator', 'Patient'],
			},
			'Education': {
				'allow_roles': ['Academics User', 'Student', 'Instructor'],
			}
		}
		if domain in data:
			return frappe._dict(data[domain])
		return None
