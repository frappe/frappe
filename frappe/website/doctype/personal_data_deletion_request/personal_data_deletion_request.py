# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

import json
import re

import frappe
from frappe import _
from frappe.core.utils import find
from frappe.model.document import Document
from frappe.utils import get_fullname
from frappe.utils.user import get_system_managers
from frappe.utils.verified_command import get_signed_params, verify_request


class PersonalDataDeletionRequest(Document):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.user_data_fields = frappe.get_hooks("user_data_fields")
		self.full_match_privacy_docs = [x for x in self.user_data_fields if x.get("redact_fields")]
		self.partial_privacy_docs = [
			x for x in self.user_data_fields if x.get("partial") or not x.get("redact_fields")
		]
		self.anonymization_value_map = {
			"Code": "[REDACTED]: Removed due to Personal Data Deletion Request",
			"Data": "[REDACTED]",
			"Date": "1111-01-01",
			"Int": 0,
			"Phone": "+91 0000000000",
			"Name": "REDACTED",
		}

	def autoname(self):
		from frappe.model.naming import set_name_from_naming_options

		pattern = re.compile(
			r"^(([a-zA-Z]{1})|([a-zA-Z]{1}[a-zA-Z]{1})|"
			r"([a-zA-Z]{1}[0-9]{1})|([0-9]{1}[a-zA-Z]{1})|"
			r"([a-zA-Z0-9][-_.a-zA-Z0-9]{0,61}[a-zA-Z0-9]))\."
			r"([a-zA-Z]{2,13}|[a-zA-Z0-9-]{2,30}.[a-zA-Z]{2,3})$"
		)
		domain = frappe.local.site.replace("_", "-")
		site = domain if pattern.match(domain) else f"{domain}.com"
		autoname = f"format:deleted-user-{{####}}@{site}"
		set_name_from_naming_options(autoname, self)
		frappe.utils.validate_email_address(self.email, throw=True)

	def after_insert(self):
		self.send_verification_mail()

	def generate_url_for_confirmation(self):
		params = {"email": self.email, "name": self.name, "host_name": frappe.local.site}
		api = frappe.utils.get_url(
			"/api/method/frappe.website.doctype.personal_data_deletion_request"
			".personal_data_deletion_request.confirm_deletion"
		)
		url = f"{api}?{get_signed_params(params)}"

		if frappe.conf.developer_mode:
			print(f"URL generated for {self.doctype} {self.name}: {url}")

		return url

	def disable_user(self):
		user = frappe.get_doc("User", self.email)
		user.enabled = False
		user.save()

	def send_verification_mail(self):
		url = self.generate_url_for_confirmation()

		frappe.sendmail(
			recipients=self.email,
			subject=_("Confirm Deletion of Data"),
			template="delete_data_confirmation",
			args={
				"email": self.email,
				"name": self.name,
				"host_name": frappe.local.site,
				"link": url,
			},
			header=[_("Confirm Deletion of Data"), "green"],
		)

	def notify_system_managers(self):
		system_managers = get_system_managers(only_name=True)

		frappe.sendmail(
			recipients=system_managers,
			subject=_("User {0} has requested for data deletion").format(self.email),
			template="data_deletion_approval",
			args={"user": self.email, "url": frappe.utils.get_url(self.get_url())},
			header=[_("Approval Required"), "green"],
		)

	def validate_data_anonymization(self):
		frappe.only_for("System Manager")

		if self.status != "Pending Approval":
			frappe.throw(_("This request has not yet been approved by the user."))

	@frappe.whitelist()
	def trigger_data_deletion(self):
		"""Redact user data defined in current site's hooks under `user_data_fields`"""
		self.validate_data_anonymization()
		self.disable_user()
		self.anonymize_data()

	def anonymize_data(self):
		return frappe.enqueue_doc(
			self.doctype,
			self.name,
			"_anonymize_data",
			queue="long",
			timeout=3000,
			now=frappe.flags.in_test,
		)

	def add_deletion_steps(self):
		if self.deletion_steps:
			return

		for step in self.full_match_privacy_docs + self.partial_privacy_docs:
			row_data = {
				"status": "Pending",
				"document_type": step.get("doctype"),
				"partial": step.get("partial") or False,
				"fields": json.dumps(step.get("redact_fields", [])),
				"filtered_by": step.get("filtered_by") or "",
			}
			self.append("deletion_steps", row_data)

		self.anonymization_matrix = json.dumps(self.anonymization_value_map, indent=4)
		self.save()
		self.reload()

	def redact_partial_match_data(self, doctype):
		self.__redact_partial_match_data(doctype)
		self.rename_documents(doctype)

	def rename_documents(self, doctype):
		if not doctype.get("rename"):
			return

		def new_name(email, number):
			email_user, domain = email.split("@")
			return f"{email_user}-{number}@{domain}"

		for i, name in enumerate(
			frappe.get_all(
				doctype["doctype"],
				filters={doctype.get("filter_by", "owner"): self.email},
				pluck="name",
			)
		):
			frappe.rename_doc(
				doctype["doctype"], name, new_name(self.anon, i + 1), force=True, show_alert=False
			)

	def redact_full_match_data(self, ref, email):
		"""Replaces the entire field value by the values set in the anonymization_value_map"""
		filter_by = ref.get("filter_by", "owner")

		docs = frappe.get_all(
			ref["doctype"],
			filters={filter_by: email},
			fields=["name", filter_by],
		)

		# skip if there are no Documents
		if not docs:
			return

		self.anonymize_fields_dict = self.generate_anonymization_dict(ref)

		for doc in docs:
			self.redact_doc(doc, ref)

	def generate_anonymization_dict(self, ref):
		anonymize_fields_dict = {}
		meta = frappe.get_meta(ref["doctype"])

		for field in ref.get("redact_fields", []):
			field_details = meta.get_field(field)

			if not field_details:
				print(f"Incorrect personal_field {field} defined in hooks")
				continue

			field_value = (
				self.anon
				if field_details.unique
				else (
					self.anonymization_value_map.get(field_details.options)
					or self.anonymization_value_map.get(field_details.fieldtype)
					or field
				)
			)
			anonymize_fields_dict[field] = field_value

		return anonymize_fields_dict

	def redact_doc(self, doc, ref):
		filter_by = ref.get("filter_by", "owner")
		meta = frappe.get_meta(ref["doctype"])
		filter_by_meta = meta.get_field(filter_by)

		if filter_by_meta and filter_by_meta.fieldtype != "Link":

			if self.email in doc[filter_by]:
				value = re.sub(self.full_name_regex, self.anonymization_value_map["Data"], doc[filter_by])
				value = re.sub(self.email_regex, self.anon, value)
				self.anonymize_fields_dict[filter_by] = value

		frappe.db.set_value(
			ref["doctype"],
			doc["name"],
			self.anonymize_fields_dict,
			modified_by="Administrator",
		)

		if ref.get("rename") and doc["name"] != self.anon:
			frappe.rename_doc(ref["doctype"], doc["name"], self.anon, force=True, show_alert=False)

	def _anonymize_data(self, email=None, anon=None, set_data=True, commit=False):
		email = email or self.email
		anon = anon or self.name

		if set_data:
			self.__set_anonymization_data(email, anon)

		self.add_deletion_steps()

		self.full_match_doctypes = (
			x
			for x in self.full_match_privacy_docs
			if filter(lambda x: x.document_type == x and x.status == "Pending", self.deletion_steps)
		)

		self.partial_match_doctypes = (
			x
			for x in self.partial_privacy_docs
			if filter(lambda x: x.document_type == x and x.status == "Pending", self.deletion_steps)
		)

		for doctype in self.full_match_doctypes:
			self.redact_full_match_data(doctype, email)
			self.set_step_status(doctype["doctype"])
			if commit:
				frappe.db.commit()

		for doctype in self.partial_match_doctypes:
			self.redact_partial_match_data(doctype)
			self.set_step_status(doctype["doctype"])
			if commit:
				frappe.db.commit()

		frappe.rename_doc("User", email, anon, force=True, show_alert=False)
		self.db_set("status", "Deleted")
		if commit:
			frappe.db.commit()

	def set_step_status(self, step, status="Deleted"):
		del_step = find(self.deletion_steps, lambda x: x.document_type == step and x.status != status)

		if not del_step:
			del_step = find(self.deletion_steps, lambda x: x.document_type == step)

		del_step.status = status
		self.save()
		self.reload()

	def __set_anonymization_data(self, email, anon):
		self.anon = anon or self.name
		self.full_name = get_fullname(email)
		self.email_regex = get_pattern(email)
		self.full_name_regex = get_pattern(self.full_name)
		self.is_full_name_set = email != self.full_name
		self.anonymization_value_map["Email"] = self.anon

	def __redact_partial_match_data(self, doctype):
		match_fields = []
		editable_text_fields = {
			"Small Text",
			"Text",
			"Text Editor",
			"Code",
			"HTML Editor",
			"Markdown Editor",
			"Long Text",
			"Data",
		}

		for df in frappe.get_meta(doctype["doctype"]).fields:
			if df.fieldtype not in editable_text_fields:
				continue

			match_fields += [
				f"`{df.fieldname}`= REPLACE(REPLACE(`{df.fieldname}`, %(name)s,"
				f" 'REDACTED'), %(email)s, '{self.anon}')",
			]

		update_predicate = f"SET  {', '.join(match_fields)}"
		where_predicate = (
			"" if doctype.get("strict") else f"WHERE `{doctype.get('filter_by', 'owner')}` = %(email)s"
		)

		frappe.db.sql(
			f"UPDATE `tab{doctype['doctype']}` {update_predicate} {where_predicate}",
			{"name": self.full_name, "email": self.email},
		)


def remove_unverified_record():
	frappe.db.sql(
		"""
		DELETE FROM `tabPersonal Data Deletion Request`
		WHERE `status` = 'Pending Verification'
		AND `creation` < (NOW() - INTERVAL '7' DAY)"""
	)


@frappe.whitelist(allow_guest=True)
def confirm_deletion(email, name, host_name):
	if not verify_request():
		return

	doc = frappe.get_doc("Personal Data Deletion Request", name)
	host_name = frappe.local.site

	if doc.status == "Pending Verification":
		doc.status = "Pending Approval"
		doc.save(ignore_permissions=True)
		doc.notify_system_managers()
		frappe.db.commit()
		frappe.respond_as_web_page(
			_("Confirmed"),
			_("The process for deletion of {0} data associated with {1} has been initiated.").format(
				host_name, email
			),
			indicator_color="green",
		)

	else:
		frappe.respond_as_web_page(
			_("Link Expired"),
			_("This link has already been activated for verification."),
			indicator_color="red",
		)


def get_pattern(full_match):
	return re.compile(r"(?<!\.)\b{0}\b(?!\.)".format(re.escape(full_match)))
