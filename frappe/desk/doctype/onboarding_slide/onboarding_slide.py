# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe import _
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files

class OnboardingSlide(Document):
	def validate(self):
		if self.slide_type == 'Continue' and frappe.db.exists('Onboarding Slide', {'slide_type': 'Continue', 'name': ('!=', self.name)}):
			frappe.throw(_('An Onboarding Slide of Slide Type Continue already exists.'))

		if self.slide_order:
			same_order_slide = frappe.db.exists('Onboarding Slide', {'slide_order': self.slide_order, 'name': ('!=', self.name)})
			if same_order_slide:
				frappe.throw(_('An Onboarding Slide <b>{0}</b> with the same slide order already exists').format(same_order_slide))

	def on_update(self):
		if self.ref_doctype:
			module = frappe.db.get_value('DocType', self.ref_doctype, 'module')
		else:
			module = self.slide_module
		export_to_files(record_list=[['Onboarding Slide', self.name]], record_module=module)

def get_onboarding_slides_as_list():
	slides = []
	slide_docs = frappe.db.get_all('Onboarding Slide',
		filters={'is_completed': 0},
		or_filters={'slide_order': ('!=', 0), 'slide_type': 'Continue'},
		order_by='slide_order')

	# to check if continue slide is required
	first_slide = get_first_slide()

	for entry in slide_docs:
		# using get_doc because child table fields are not fetched in get_all
		slide_doc = frappe.get_doc('Onboarding Slide', entry.name)
		if frappe.scrub(slide_doc.app) in frappe.get_installed_apps():
			slide = frappe._dict(
				slide_type=slide_doc.slide_type,
				title=slide_doc.slide_title,
				help=slide_doc.slide_desc,
				fields=slide_doc.slide_fields,
				help_links=get_help_links(slide_doc),
				add_more=slide_doc.add_more_button,
				max_count=slide_doc.max_count,
				image_src=get_slide_image(slide_doc),
				ref_doctype=slide_doc.ref_doctype,
				app=slide_doc.app
			)
			if slide.slide_type == 'Continue':
				if is_continue_slide_required(first_slide):
					slides.insert(0, slide)
			else:
				slides.append(slide)

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

def is_continue_slide_required(first_slide):
	# check if first slide itself is not completed
	if not first_slide.is_completed:
		return False

	# check if there is any active slide which is not completed
	return frappe.db.exists('Onboarding Slide', {
		'is_completed': 0,
		'slide_order': ('!=', 0),
		'slide_type': ('!=', 'Continue')
	})

@frappe.whitelist()
def create_onboarding_docs(values, doctype=None, app=None, slide_type=None):
	data = json.loads(values)
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

@frappe.whitelist()
def mark_slide_as_completed(slide_title):
	frappe.db.set_value('Onboarding Slide', slide_title, 'is_completed', 1)

def get_first_slide():
	slides = frappe.db.get_all('Onboarding Slide',
		filters={'slide_order': ('!=', 0), 'slide_type': ('!=', 'Continue')},
		order_by='slide_order',
		fields=['name', 'is_completed']
	)
	return slides[0]