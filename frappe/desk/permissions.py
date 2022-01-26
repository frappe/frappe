# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe

@frappe.whitelist()
def get_permissions():
	'''Get permissions of the current user'''
	return DeskPermissions().get()

class DeskPermissions:
	def get(self):
		self.doctypes = dict()
		self.roles = frappe.get_roles()
		self.build_doctypes()
		# self.build_pages_and_reports('Role Permission for Page and Report')
		# self.build_pages_and_reports('Custom Role')
		return dict(
			doctypes = self.doctypes,
			# reports = self.reports,
			# pages = self.pages
		)

	def build_doctypes(self):
		perms = self.get_permissions_for('DocPerm')
		perms = perms + self.get_permissions_for('Custom DocPerm')
		# shared
		for d in frappe.get_all('DocShare', fields=['share_doctype'], filters=dict(user = frappe.session.user, read=1)):
			perms.append(frappe._dict(parent=d.share_doctype, read=1))

		self.make_doctype_map(perms)
		return perms

	def make_doctype_map(self, perms):
		active_domains = frappe.get_active_domains()
		for d in perms:
			if d.parent in self.doctypes:
				for key in ('read', 'write', 'create'):
					if d.get(key):
						self.doctypes[d.parent][key] = 1
			else:
				self.doctypes[d.parent] = self.get_doctype_perm(d, active_domains)

	def get_doctype_perm(self, d, active_domains):
		'''Get additional restrictions to the doctype'''
		perm = frappe._dict(read=d.read, write=d.write, create=d.create)
		try:
			perm.no_read, perm.no_create, perm.domain, perm.is_single = \
					frappe.db.get_value('DocType', d.parent, ['read_only', 'in_create', 'restrict_to_domain', 'issingle'])
		except TypeError:
			# docperm without doctype (legacy?), continue
			perm.restricted = 1
		if active_domains and perm.domain in active_domains:
			perm.restricted = 1

		return perm

	def get_permissions_for(self, perm_doctype):
		return frappe.get_all(perm_doctype,
			fields=['parent', 'read', 'write', 'create'],
			filters = dict(permlevel=0, role=('in', self.roles)))

	def build_pages_and_reports(self, doctype):
		rules = frappe.get_all('Has Role', ('parent'), dict(parenttype = doctype))

