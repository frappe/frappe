# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files

class SetupWizardSlide(Document):
	def on_update(self):
		if self.ref_doctype:
			module = frappe.db.get_value('DocType', self.ref_doctype, 'module')
		else:
			module = self.slide_module
		export_to_files(record_list=[['Setup Wizard Slide', self.name]], record_module=module)

def get_onboarding_slides_as_list():
	slides = []
	slide_docs = frappe.get_all('Setup Wizard Slide',
		filters={'slide_order': ('!=', 0)},
		order_by='slide_order')
	for entry in slide_docs:
		# using get_doc because child table fields are not fetched in get_all
		slide_doc = frappe.get_doc('Setup Wizard Slide', entry.name)
		if frappe.scrub(slide_doc.app) in frappe.get_installed_apps():
			slides.append(frappe._dict(
				slide_type=slide_doc.slide_type,
				title=slide_doc.slide_title,
				help=slide_doc.slide_desc,
				fields=slide_doc.slide_fields,
				help_links=get_help_links(slide_doc),
				add_more=slide_doc.add_more_button,
				max_count=slide_doc.max_count,
				submit_method=slide_doc.submit_method,
				image_src=get_slide_image(slide_doc),
				ref_doctype=slide_doc.ref_doctype,
				app=slide_doc.app
			))
	return slides

@frappe.whitelist()
def get_onboarding_slides():
	slides = []
	slide_list = get_onboarding_slides_as_list()

	active_domains = frappe.get_active_domains()
	for slide in slide_list:
		if not slide.domains or any(domain in active_domains for domain in slide.domains):
			slides.append(slide)
	return slides

def get_help_links(slide_doc):
	links=[]
	for link in slide_doc.help_links:
		links.append({
			'label': link.label,
			'video_id': link.video_id
		})
	return links

def get_slide_image(slide_doc):
	if slide_doc.image_src:
		return slide_doc.image_src
	return None

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