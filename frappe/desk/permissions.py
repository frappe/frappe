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
		return dict(
			doctypes = self.doctypes,
			reports = self.get_reports(),
			pages = self.get_pages()
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

	def get_pages(self):
		HasRole = frappe.qb.DocType('Has Role')
		Page = frappe.qb.DocType('Page')

		items = (frappe.qb.from_(Page)
			.inner_join(HasRole)
				.on(Page.name == HasRole.parent)
			.select(Page.name, Page.page_name, Page.title).distinct()
			.where(HasRole.role.isin(self.roles))).run(as_dict=True)

		CustomRole = frappe.qb.DocType('Custom Role')
		items += (frappe.qb.from_(CustomRole)
			.inner_join(HasRole)
				.on(CustomRole.name == HasRole.parent)
			.inner_join(Page)
				.on(Page.name == CustomRole.page)
			.select(Page.name, Page.page_name, Page.title).distinct()
			.where(HasRole.role.isin(self.roles))).run(as_dict=True)

		return items

	def get_reports(self):
		HasRole = frappe.qb.DocType('Has Role')
		Report = frappe.qb.DocType('Report')

		items = (frappe.qb.from_(Report)
			.inner_join(HasRole)
				.on(Report.name == HasRole.parent)
			.select(Report.name, Report.report_type, Report.ref_doctype).distinct()
			.where(HasRole.role.isin(self.roles))).run(as_dict=True)

		CustomRole = frappe.qb.DocType('Custom Role')
		items += (frappe.qb.from_(CustomRole)
			.inner_join(HasRole)
				.on(CustomRole.name == HasRole.parent)
			.inner_join(Report)
				.on(Report.name == CustomRole.report)
			.select(Report.name, Report.report_type, Report.ref_doctype).distinct()
			.where(HasRole.role.isin(self.roles))).run(as_dict=True)

		return items

