# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import json

class ManageCustomization(Document):
	pass

@frappe.whitelist()
def export_customizations():
	"""Export fixtures as JSON"""

	export_customizations_doc = frappe.get_single("Manage Customization")
	customizations = []

	for doctype in export_customizations_doc.export_customization:
		filters, or_filters = {}, {}

		if doctype.get("filters"):
			filters = json.loads(doctype.get("filters"))
		if doctype.get("or_filters"):
			or_filters = json.loads(doctype.get("or_filters"))

		docs = frappe.get_all(doctype.get("document_type"), filters=filters, or_filters=or_filters)
		length = len(docs)
		for idx, doc in enumerate(docs):
			frappe.publish_realtime("exporting_progress", dict(progress=idx, total=length, message=doctype.get("document_type")), user=frappe.session.user)
			customizations.append(frappe.get_doc(doctype.get("document_type"), doc.name).as_dict())

	return frappe._dict({
		"data": post_process(customizations)
	})

@frappe.whitelist()
def import_customizations():
	"""Import fixtures as JSON"""

	import_file = frappe.get_all("File", filters={
		"attached_to_doctype": "Manage Customization",
		"attached_to_name": "Manage Customization"
	}, limit=1, order_by="creation desc")

	if not import_file:
		return

	content = json.loads(frappe.get_doc("File", import_file[0].name).get_content())
	length = len(content)

	for idx, doc in enumerate(content.get("message").get("data")):
		frappe.publish_realtime("exporting_progress", dict(progress=idx, total=length, message=doc.get("doctype")), user=frappe.session.user)
		frappe.get_doc(doc).insert(ignore_permissions=True, ignore_if_duplicate=True)

def post_process(customizations):
	del_keys = ('modified_by', 'creation', 'owner', 'idx', 'name', 'modified', 'docstatus')

	for doc in customizations:
		for key in del_keys:
			if key in doc:
				del doc[key]

		for key, value in doc.items():
			if not isinstance(value, list):
				continue

			for child in value:
				for key in del_keys:
					if key in child:
						del child[key]

	return customizations

@frappe.whitelist()
def download_customization_json():
	data = frappe._dict(frappe.local.form_dict)
	frappe.response['filename'] = 'Customizations.json'
	frappe.response['filecontent'] = data.get("data")
	frappe.response['content_type'] = 'application/json'
	frappe.response['type'] = 'download'