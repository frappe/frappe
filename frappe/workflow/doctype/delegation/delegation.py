# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
# import frappe
from frappe.model.document import Document

class Delegation(Document):
	pass

def get_permission_query_conditions(user):
	if not user: user = frappe.session.user

	if user == "Administrator": return ""

	return "(`tabDelegation`.`delegator`='{user}' or `tabDelegation`.`delegatee`='{user}')".format(user=user)

def has_permission(doc, user):
	if user not in ['Administrator', doc.delegator, doc.delegatee]:
		return False
