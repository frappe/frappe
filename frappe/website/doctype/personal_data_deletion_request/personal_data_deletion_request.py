# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import re
from frappe.model.document import Document
from frappe.utils.verified_command import get_signed_params, verify_request

class PersonalDataDeletionRequest(Document):
	def after_insert(self):
		if self.email in ['Administrator', 'Guest']:
			frappe.throw(_("This user's data cannot be requested for deletion"))
		else:
			self.send_verification_mail()

	def send_verification_mail(self):
		url = frappe.utils.get_url("/api/method/frappe.website.doctype.personal_data_delete_request.personal_data_delete_request.confirm_deletion") +\
		"?" + get_signed_params({"email": self.email, "name": self.name})
		host_name = frappe.local.site

		frappe.sendmail(recipients= self.email,
		subject=_("Confirm Deletion of Data"),
		template="delete_data_confirmation",
		args={'email':self.email, 'link':url, 'host_name':host_name},
		header=[_("Confirm Deletion of Data"), "green"])

	def anonymize_data(self):
		if not ('System Manager' in frappe.get_roles(frappe.session.user) and self.status == 'Pending Approval'):
			frappe.throw(_("You are not authorized to complete this action."))

		privacy_docs = frappe.get_hooks("user_privacy_documents")

		anonymize_value_map = {
			'Date': '1111-01-01',
			'Int': 0,
			'Code': 'http://xxxxx'}

		regex = re.compile(r"(?<!\.)\b{0}\b(?!\.)".format(re.escape(self.email)))

		for ref_doc in privacy_docs:
			meta = frappe.get_meta(ref_doc['doctype'])
			personal_fields = ref_doc.get('personal_fields', [])

			if ref_doc.get('applies_to_website_user') and 'Guest' not in frappe.get_roles(self.email):
				continue

			anonymize_fields = ''
			for field in personal_fields:
				field_details = meta.get_field(field)
				field_value = anonymize_value_map.get(field_details.fieldtype, str(field)) if not field_details.unique else self.name
				anonymize_fields += ', `{0}`= \'{1}\''.format(field, field_value)

			if (meta.get_field(ref_doc['match_field']) or {}).get('fieldtype') == 'Code':
				self.anonymize_multi_email_record(ref_doc, anonymize_fields, regex)

			else:
				frappe.db.sql("""UPDATE `tab{0}`
					SET `{1}` = '{2}' {3}
					WHERE `{1}` = '{4}' """.format(ref_doc['doctype'], ref_doc['match_field'], self.name,#nosec
						anonymize_fields, self.email))

	def anonymize_multi_email_record(self, ref_doc, anonymize_fields, regex):
		docs = frappe.get_all(ref_doc['doctype'], {ref_doc['match_field']:('like', '%'+self.email+'%')}, ['name', ref_doc['match_field']])
		for d in docs:
			if not re.search(regex, d[ref_doc['match_field']]):
				continue

			anonymize_match_value = ', '.join(map(lambda x: self.name if re.search(regex, x) else x, d[ref_doc['match_field']].split()))
			frappe.db.sql("""UPDATE `tab{0}`
				SET `{1}` = '{2}' {3}
				WHERE `name` = '{4}' """.format(ref_doc['doctype'], ref_doc['match_field'], anonymize_match_value,#nosec
				anonymize_fields, d['name']))

def remove_unverified_record():
	frappe.db.sql("""DELETE FROM `tabPersonal Data Deletion Request` WHERE `status` = 'Pending Verification' and `creation` < (NOW() - INTERVAL '7' DAY)""")

@frappe.whitelist(allow_guest=True)
def confirm_deletion(email, name):
	if not verify_request():
		return
	doc  = frappe.get_doc("Personal Data Delete Request", name)
	if doc.status != 'Pending Approval':
		doc.status = 'Pending Approval'
		doc.save(ignore_permissions=True)
		frappe.db.commit()
	host_name = frappe.local.site
	frappe.respond_as_web_page(_("Confirmed"),
		_("The process for deletion of {0} Data associated with {1} has been initiated.").format(host_name, email),
		indicator_color='green')