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
			personal_data = get_user_data(self.user)
			self.generate_file_and_send_mail(personal_data)

	def generate_file_and_send_mail(self, personal_data):
		"""generate the file link for download"""
		user_name = self.user_name.replace(' ','-')
		f = frappe.get_doc({
			'doctype': 'File',
			'file_name': 'Personal-Data-'+user_name+'-'+self.name+'.json',
			"attached_to_doctype": 'Personal Data Download Request',
			"attached_to_name": self,
			'content': str(personal_data),
			'is_private': True
		})
		f.save()
		frappe.sendmail(recipients= self.user,
		subject=_("ERPNext: User Data"),
		message= _("Your data is ready, <a href="+f.file_url+" download>Click here to download your data</a>"),
		header=[_("ERPNext: User Data"), "green"])

def get_user_data(user):
	""" returns user data not linked to User doctype """
	hooks = frappe.get_hooks("user_privacy_documents")
	data = {}
	for hook in hooks:
		d = []
		for email_field in hook.get('email_field'):
			d += frappe.get_all(hook.get('doctype'), {email_field: user},["*"])
		if d:
			data.update({ hook.get('doctype'):d })
	return data