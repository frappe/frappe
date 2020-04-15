# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
import datetime
import base64
from frappe.model.document import Document
from frappe.utils.file_manager import save_file, get_file
from frappe import _
from six import string_types
from frappe.frappeclient import FrappeClient
from frappe.model.naming import make_autoname
from frappe.utils.password import get_decrypted_password

class Package(Document):
	def import_from_package(self):
		filters = {"attached_to_doctype": "Package", "attached_to_name": "Package"}
		files = frappe.get_list("File", filters=filters, limit=1, order_by="creation desc")
		if not files:
			frappe.msgprint(_("No file attach for Importing."))
			return

		for f in files:
			fname, fcontents = get_file(f.name)
			import_package(fcontents)

		frappe.msgprint(_("Package Imported."))

	def deploy_package(self):
		package = export_package()

		for dt_file in frappe.get_list("File", filters={"attached_to_doctype": "Release", "attached_to_name": "Release"}):
			frappe.delete_doc_if_exists("File", dt_file.name)

		file_name = make_autoname("Package")
		save_file(file_name, json.dumps(package), "Package", "Package")

		length = len(self.instances)
		for idx, instance in enumerate(self.instances):
			frappe.publish_realtime("package",  {"progress": idx, "total": length, "message": instance.instance_url, "prefix": _("Deploying")},
				user=frappe.session.user)

			self.install_package_to_remote(package, instance)

	def install_package_to_remote(self, package, instance):
		print((instance.doctype, instance.name))
		try:
			connection = FrappeClient(instance.instance_url, instance.username, get_decrypted_password(instance.doctype, instance.name))
		except Exception:
			frappe.log_error(frappe.get_traceback())
			frappe.throw(_("Couldn't connect to site {0}. Please check Error Logs.").format(instance.instance_url))

		try:
			connection.post_request({
				"cmd": "frappe.custom.doctype.package.package.import_package",
				"package": json.dumps(package)
			})
		except Exception:
			frappe.log_error(frappe.get_traceback())
			frappe.throw(_("Error while installing package to site {0}. Please check Error Logs.").format(instance.instance_url))

@frappe.whitelist()
def export_package():
	"""Export package as JSON."""
	package_doc = frappe.get_single("Package")
	package = []

	for doctype in package_doc.package_details:
		filters = []

		if doctype.get("filters_json"):
			filters = json.loads(doctype.get("filters_json"))

		docs = frappe.get_all(doctype.get("document_type"), filters=filters)
		length = len(docs)

		for idx, doc in enumerate(docs):
			frappe.publish_realtime("package", {
					"progress":idx, "total":length,
					"message":doctype.get("document_type"),
					"prefix": _("Exporting")
				},
				user=frappe.session.user)

			document = frappe.get_doc(doctype.get("document_type"), doc.name).as_dict()
			attachments = []

			if doctype.attachments:
				filters = {
					"attached_to_doctype": document.get("doctype"),
					"attached_to_name": document.get("name")
				}

				for f in frappe.get_list("File", filters=filters):
					fname, fcontents = get_file(f.name)
					attachments.append({
						"fname": fname,
						"content": base64.b64encode(fcontents).decode('ascii')
					})

			document.update({
				"attachments": attachments,
				"overwrite": True if doctype.overwrite else False
			})

			package.append(document)

	return post_process(package)

@frappe.whitelist()
def import_package(package=None):
	"""Import package from JSON."""
	if isinstance(package, string_types):
		package = json.loads(package)

	for doc in package:
		modified = doc.pop("modified")
		overwrite = doc.pop("overwrite")
		attachments = doc.pop("attachments")
		exists = frappe.db.exists(doc.get("doctype"), doc.get("name"))

		if not exists:
			d = frappe.get_doc(doc).insert(ignore_permissions=True, ignore_if_duplicate=True)
			if attachments:
				add_attachment(attachments, d)
		else:
			docname = doc.pop("name")
			document = frappe.get_doc(doc.get("doctype"), docname)

			if overwrite:
				update_document(document, doc, attachments)

			else:
				if frappe.utils.get_datetime(document.modified) < frappe.utils.get_datetime(modified):
					update_document(document, doc, attachments)

def update_document(document, doc, attachments):
	document.update(doc)
	document.save()
	if attachments:
		add_attachment(attachments, document)

def add_attachment(attachments, doc):
	for attachment in attachments:
		save_file(attachment.get("fname"), base64.b64decode(attachment.get("content")), doc.get("doctype"), doc.get("name"))

def post_process(package):
	"""Remove the keys from Document and Child Document. Convert datetime, date, time to str."""
	del_keys = ('modified_by', 'creation', 'owner', 'idx', 'docstatus')
	child_del_keys = ('modified_by', 'creation', 'owner', 'idx', 'docstatus', 'name')

	for doc in package:
		for key in del_keys:
			if key in doc:
				del doc[key]

		for key, value in doc.items():
			stringified_value = get_stringified_value(value)
			if stringified_value:
				doc[key] = stringified_value

			if not isinstance(value, list):
				continue

			for child in value:
				for child_key in child_del_keys:
					if child_key in child:
						del child[child_key]

				for child_key, child_value in child.items():
					stringified_value = get_stringified_value(child_value)
					if stringified_value:
						child[child_key] = stringified_value

	return package

def get_stringified_value(value):
	if isinstance(value, datetime.datetime):
		return frappe.utils.get_datetime_str(value)

	if isinstance(value, datetime.date):
		return frappe.utils.get_date_str(value)

	if isinstance(value, datetime.timedelta):
		return frappe.utils.get_time_str(value)

	return None
