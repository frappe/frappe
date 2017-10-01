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
	''' Enable/Disable roles as per the settings and reflect the same in current user '''
	def remove_role(role):
		frappe.db.sql('delete from `tabHas Role` where role=%s', role)
		frappe.set_value('Role', role, 'disabled', 1)

	active_domains = json.loads(active_domains)
	user = frappe.get_doc("User", frappe.session.user)

	add, remove = [], []
	for domain in active_domains:
		data = get_domain(domain)
		if data.allow_roles:
			add.extend(data.allow_roles)
		if data.remove_roles:
			remove.extend(data.remove_roles)

	remove_roles = [role for role in remove if role not in add] # If a domain is unticked

	for role in frappe.get_all('Role', filters = {'disabled': 1}, fields=["name"]):
		if role.name in add:
			frappe.set_value('Role', role.name, 'disabled', 0) # Enable Roles for a domain

	# Remove roles from current user and disable that role
	if remove_roles:
		for role in remove_roles:
			remove_role(role)
	user.add_roles(*add)

def get_domain(domain):
		data = {
			'Healthcare': {
				'allow_roles': ['Physician', 'Nursing User', 'Laboratory User',
					'LabTest Approver', 'Healthcare Administrator', 'Patient'],
				'remove_roles': ['Manufacturing User', 'Manufacturing Manager', 'Academics User', 'Instructor'],
			},
			'Manufacturing': {
				'allow_roles': ['Manufacturing User', 'Manufacturing Manager', 'Projects User', 'Projects Manager'],
				'remove_roles': ['Academics User', 'Instructor', 'Physician', 'Nursing User',
				'Laboratory User', 'LabTest Approver', 'Healthcare Administrator'],
			},
		}
		if domain not in data:
			import erpnext.setup.setup_wizard.domainify as domainify
			return frappe._dict(domainify.get_domain(domain))
		else:
			return frappe._dict(data[domain])
