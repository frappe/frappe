# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document

class SetupWizardSlide(Document):
	pass

@frappe.whitelist()
def create_onboarding_docs(values, doctype=None, submit_method=None, app=None, slide_type=None):
	data = json.loads(values)
	if submit_method:
		try:
			method = frappe.scrub(app) + '.utilities.onboarding_utils.' + submit_method
			frappe.call(method, data)
		except AttributeError:
			create_generic_onboarding_doc(data, doctype, slide_type)
	else:
		doc = frappe.new_doc(doctype)
		if hasattr(doc, 'create_onboarding_docs'):
			doc.create_onboarding_docs(data)
		else:
			create_generic_onboarding_doc(data, doctype, slide_type)

def create_generic_onboarding_doc(data, doctype, slide_type):
	if slide_type == 'Settings':
		doc = frappe.get_single(doctype)
		for entry in data:
			doc.set(entry, data.get(entry))
		doc.save()

	elif slide_type == 'Create':
		doc = frappe.new_doc(doctype)
		for entry in data:
			doc.set(entry, data.get(entry))
		doc.flags.ignore_mandatory = True
		doc.flags.ignore_links = True
		doc.insert()