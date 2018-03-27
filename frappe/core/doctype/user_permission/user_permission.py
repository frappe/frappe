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

	def on_trash(self): # pylint: disable=no-self-use
		frappe.cache().delete_value('user_permissions')

def get_user_permissions(user=None):
	'''Get all users permissions for the user as a dict of doctype'''
	if not user:
		user = frappe.session.user

	out = frappe.cache().hget("user_permissions", user)

	if out is None:
		out = {}
		try:
			for perm in frappe.get_all('User Permission',
				fields=['allow', 'for_value'], filters=dict(user=user)):
				out.setdefault(perm.allow, []).append(perm.for_value)

			frappe.cache().hset("user_permissions", user, out)
		except frappe.SQLError as e:
			if e.args[0]==1146:
				# called from patch
				pass

	return out