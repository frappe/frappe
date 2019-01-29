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
			personal_data.update(get_linked_user_data(self.user))
			
			self.generate_file_and_send_mail(personal_data)

	def generate_file_and_send_mail(self, personal_data):
		"""generate the file link for download"""
		user_name = self.user_name.replace(' ','-')
		f = frappe.get_doc({
			'doctype': 'File',
			'file_name': 'Personal-Data-'+user_name+'.json',
			'content': str(personal_data),
			'is_private': True
		})
		f.save()
		frappe.sendmail(recipients= self.user,
		subject=_("ERPNext: User Data"),
		message= "Your data is ready, <a href="+f.file_url+" download>Click here to download your data</a>",
		header=["ERPNext: User Data", "green"])

def get_unlinked_user_data(user):
	""" returns user data not linked to User doctype """
	hooks = frappe.get_hooks("user_privacy_documents")
	data = {}
	for hook in hooks:
		d = frappe.get_all(hook.get('doctype'), {hook.get('email_field'): user},["*"])
		if d:
			data.update({ hook.get('doctype'):d })	
	return data

def get_linked_user_data(user):
	""" returns user data linked to the User doctype """
	linked_doctypes = get_linked_doctypes("Customer")
	data = {}
	for doctype in linked_doctypes:
		meta = frappe.get_meta(doctype)
		if not meta.issingle:
			d = frappe.get_all(doctype, {linked_doctypes.get(doctype).get('fieldname')[0]: user},["*"])
			if d:
				data.update({ doctype:d })
	return data