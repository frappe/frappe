# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.model.document import Document
from frappe.permissions import (get_valid_perms, update_permission_property)
from frappe import _

class UserPermission(Document):
	def on_update(self):
		frappe.cache().delete_value('user_permissions')

		if self.apply_for_all_roles:
			self.apply_user_permissions_to_all_roles()

	def apply_user_permissions_to_all_roles(self):
		# add apply user permissions for all roles that
		# for this doctype
		def show_progress(i, l):
			if l > 2:
				frappe.publish_realtime("progress",
					dict(progress=[i, l], title=_('Updating...')),
						user=frappe.session.user)


		roles = frappe.get_roles(self.user)
		linked = frappe.db.sql('''select distinct parent from tabDocField
			where fieldtype="Link" and options=%s''', self.allow)
		for i, link in enumerate(linked):
			doctype = link[0]
			for perm in get_valid_perms(doctype, self.user):
				# if the role is applicable to the user
				show_progress(i+1, len(linked))
				if perm.role in roles:
					if not perm.apply_user_permissions:
						update_permission_property(doctype, perm.role, 0,
							'apply_user_permissions', '1')

					try:
						user_permission_doctypes = json.loads(perm.user_permission_doctypes or '[]')
					except ValueError:
						user_permission_doctypes = []

					if self.allow not in user_permission_doctypes:
						user_permission_doctypes.append(self.allow)
						update_permission_property(doctype, perm.role, 0,
							'user_permission_doctypes', json.dumps(user_permission_doctypes), validate=False)

		show_progress(len(linked), len(linked))

	def on_trash(self): # pylint: disable=no-self-use
		frappe.cache().delete_value('user_permissions')

def get_user_permissions(user=None):
	'''Get all users permissions for the user as a dict of doctype'''
	if not user:
		user = frappe.session.user

	out = frappe.cache().hget("user_permissions", user)

	if not out:
		out = {}
		try:
			for perm in frappe.get_all('User Permission',
				fields=['allow', 'for_value'], filters=dict(user=user)):
				out.setdefault(perm.allow, []).append(perm.for_value)

			# add profile match
			if user not in out.get("User", []):
				out.setdefault("User", []).append(user)

			frappe.cache().hset("user_permissions", user, out)
		except frappe.SQLError as e:
			if e.args[0]==1146:
				# called from patch
				pass

	return out