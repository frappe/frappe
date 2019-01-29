# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.desk.form.linked_with import get_linked_doctypes

class PersonalDataDownloadRequest(Document):
	def after_insert(self):
		if self.user in ['Administrator', 'Guest']:
			frappe.throw(_("This user cannot request to download data"))
		else:
			personal_data = get_unlinked_user_data(self.user)

def get_unlinked_user_data(user):
	""" returns user data not linked to User doctype """
	hooks = frappe.get_hooks("user_privacy_documents")
	data = {}
	for hook in hooks:
		d = frappe.get_all(hook.get('doctype'), {hook.get('email_field'): user},["*"])
		if d:
			data.update({ hook.get('doctype'):d })	
	return data