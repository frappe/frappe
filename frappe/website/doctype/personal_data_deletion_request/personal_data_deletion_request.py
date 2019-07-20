# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import re
from frappe.model.document import Document
from frappe.utils import validate_email_address
from frappe.utils.verified_command import get_signed_params, verify_request

class PersonalDataDeletionRequest(Document):
	def validate(self):
		validate_email_address(self.email, throw=True)

	def after_insert(self):
		self.send_verification_mail()

	def send_verification_mail(self):
		host_name = frappe.local.site
		url = frappe.utils.get_url("/api/method/frappe.website.doctype.personal_data_deletion_request.personal_data_deletion_request.confirm_deletion") +\
			"?" + get_signed_params({"email": self.email, "name": self.name, 'host_name': host_name})

		frappe.sendmail(
			recipients=self.email,
			subject=_("Confirm Deletion of Data"),
			template="delete_data_confirmation",
			args={
				'email': self.email,
				'name': self.name,
				'host_name': host_name,
				'link': url
			},
			header=[_("Confirm Deletion of Data"), "green"]
		)

	def notify_system_managers(self):
		from frappe.utils.user import get_system_managers
		system_managers = get_system_managers(only_name=True)

		frappe.sendmail(
			recipients=system_managers,
			subject=_("User {0} has requested for data deletion").format(self.email),
			template="data_deletion_approval",
			args={
				'user': self.email,
				'url': frappe.utils.get_url(self.get_url())
			},
			header=[_("Approval Required"), "green"]
		)

	def anonymize_data(self):
		""" mask user data with non identifiable data """
		frappe.only_for('System Manager')
		if not (self.status == 'Pending Approval'):
			frappe.throw(_("This request has not yet been approved by the user."))

		privacy_docs = frappe.get_hooks("user_privacy_documents")

		anonymize_value_map = {
			'Date': '1111-01-01',
			'Int': 0,
			'Code': 'http://xxxxx'
		}

		regex = re.compile(r"(?<!\.)\b{0}\b(?!\.)".format(re.escape(self.email)))

		for ref_doc in privacy_docs:
			meta = frappe.get_meta(ref_doc['doctype'])
			personal_fields = ref_doc.get('personal_fields', [])

			if ref_doc.get('applies_to_website_user') and 'Guest' not in frappe.get_roles(self.email):
				continue

			anonymize_fields = ''
			for field in personal_fields:
				field_details = meta.get_field(field)
				field_value = anonymize_value_map.get(field_details.fieldtype, str(field)) if not field_details.unique else self.name.split("@")[0]
				anonymize_fields += ', `{0}`= \'{1}\''.format(field, field_value)

			docs = frappe.get_all(ref_doc['doctype'], {ref_doc['match_field']:('like', '%'+self.email+'%')}, ['name', ref_doc['match_field']])
			for d in docs:
				if not re.search(regex, d[ref_doc['match_field']]):
					continue

				anonymize_match_value = ', '.join(map(lambda x: self.name if re.search(regex, x) else x, d[ref_doc['match_field']].split()))
				frappe.db.sql("""UPDATE `tab{0}`
					SET `{1}` = '{2}' {3}
					WHERE `name` = '{4}' """.format( #nosec
					ref_doc['doctype'],
					ref_doc['match_field'],
					anonymize_match_value,
					anonymize_fields,
					d['name']
				))
		self.db_set('status', 'Deleted')

def remove_unverified_record():
	frappe.db.sql("""
		DELETE FROM `tabPersonal Data Deletion Request`
		WHERE `status` = 'Pending Verification'
		AND `creation` < (NOW() - INTERVAL '7' DAY)""")

@frappe.whitelist(allow_guest=True)
def confirm_deletion(email, name, host_name):
	if not verify_request():
		return

	doc = frappe.get_doc("Personal Data Deletion Request", name)
	host_name = frappe.local.site
	if doc.status == 'Pending Verification':
		doc.status = 'Pending Approval'
		doc.save(ignore_permissions=True)
		doc.notify_system_managers()
		frappe.db.commit()
		frappe.respond_as_web_page(_("Confirmed"),
			_("The process for deletion of {0} data associated with {1} has been initiated.").format(host_name, email),
			indicator_color='green')
	else:
		frappe.respond_as_web_page(_("Link Expired"),
			_("This link has already been activated for verification."),
			indicator_color='red')