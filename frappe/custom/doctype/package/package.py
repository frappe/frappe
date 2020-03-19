# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
import datetime
from frappe.model.document import Document
from frappe.core.doctype.version.version import get_diff
from frappe.utils.file_manager import save_file
from frappe import _

class Package(Document):
	pass

@frappe.whitelist()
def export_package():
	"""Export package as JSON"""

	package_doc = frappe.get_single("Package")
	package = []

	for doctype in package_doc.export_package:
		filters = []

		if doctype.get("filters_json"):
			filters = json.loads(doctype.get("filters_json"))

		docs = frappe.get_all(doctype.get("document_type"), filters=filters)
		length = len(docs)

		for idx, doc in enumerate(docs):
			frappe.publish_realtime("package", {"progress":idx, "total":length, "message":doctype.get("document_type"), "prefix": _("Exporting")},
				user=frappe.session.user)

			document = frappe.get_doc(doctype.get("document_type"), doc.name).as_dict()

			if doctype.attachments:
				attachments = []
				filters = {"attached_to_doctype": document.get("doctype"), "attached_to_name": document.get("doctype")}
				for f in frappe.get_list("File", filters=filters):
					attachments.append({
						"fname": f.name,
						"content": frappe.get_doc("File", f.name).get_content()
					})

				document.update({"attachments": json.dumps(attachments)})

			if doctype.overwrite:
				document.update({"overwrite": 1})

			document.update({"modified": frappe.utils.get_datetime_str(document.get("modified"))})
			package.append(document)

	return post_process(package)

@frappe.whitelist()
def import_package(package=None):
	"""Import package from JSON"""

	content = json.loads(package)
	length = len(content)

	for doc in content:
		docname = doc.pop("name")
		modified = doc.pop("modified")
		overwrite = doc.pop("overwrite")
		exists = frappe.db.exists(doc.get("doctype"), docname)

		if not exists:
			d = frappe.get_doc(doc).insert(ignore_permissions=True, ignore_if_duplicate=True)
			if doc.get("attachments"):
				add_attachment(doc.get("attachments"), d)
		elif exists and overwrite:
			document = frappe.get_doc(doc.get("doctype"), doc.pop("name"))
			if frappe.utils.get_datetime(document.modified) < frappe.utils.get_datetime(modified):
				document.update(doc)
				document.save()
				if doc.get("attachments"):
					add_attachment(doc.get("attachments"), document)

def add_attachment(attachments, doc):
	for attachment in attachments:
		save_file(attachment.get("fname"), attachment.get("content"), doc.get("doctype"), doc.get("name"))

def post_process(package):
	"""
		Remove the keys from Document and Child Document
		Convert datetime, date, time to str
	"""
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