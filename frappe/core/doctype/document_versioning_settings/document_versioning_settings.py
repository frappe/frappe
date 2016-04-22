# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

import json


class DocumentVersioningSettings(Document):
	pass

@frappe.whitelist()
def get_modules():
	modules = frappe.db.get_all('Module def')
	settings_doc = frappe.client.get("Document Versioning Settings")
	settings = json.loads(settings_doc['stored_modules'])
	for module in modules:
		module['value'] = settings[module['name']]
	return frappe.render_template(
        'frappe/core/doctype/document_versioning_settings/document_versioning_settings.html',
		{'modules': modules})

@frappe.whitelist()
def save_modules(modules):
	doc = frappe.model.document.get_doc("Document Versioning Settings")
	doc.stored_modules = modules
	doc.save()
