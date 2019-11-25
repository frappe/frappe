# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.modules import get_module_path, scrub_dt_dn
from frappe.modules.export_file import export_to_files, create_init_py

class SetupWizardSettings(Document):
	def on_update(self):
		if frappe.flags.in_import or frappe.flags.in_test:
			return

		if frappe.local.conf.get('developer_mode'):
			record_list = [['Setup Wizard Settings', self.name]]

			for s in self.slide_order:
				record_list.append(['Setup Wizard Slide', s.slide])

			export_to_files(record_list=record_list, record_module='Desk')

			for s in self.slide_order:
				dt, dn = scrub_dt_dn('Setup Wizard Slide', s.slide)
				create_init_py(get_module_path('Desk'), dt, dn)

def get_slide_settings():
	slides = []
	slide_settings = frappe.get_single('Setup Wizard Settings')
	for entry in slide_settings.slide_order:
		slide_doc = frappe.get_doc('Setup Wizard Slide', entry.slide)
		if frappe.scrub(slide_doc.app) in frappe.get_installed_apps():
			slides.append(frappe._dict(
				slide_type = slide_doc.slide_type,
				title = slide_doc.slide_title,
				help = slide_doc.slide_desc,
				domains = get_domains(slide_doc),
				fields = slide_doc.slide_fields,
				help_links = get_help_links(slide_doc),
				add_more = slide_doc.add_more_button,
				max_count = slide_doc.max_count,
				submit_method = get_submit_method(slide_doc),
				image_src = get_slide_image(slide_doc)
			))
	return slides

@frappe.whitelist()
def get_onboarding_slides():
	slides = []
	slide_settings = get_slide_settings()

	domains = frappe.get_active_domains()
	for s in slide_settings:
		if not s.domains or any(d in domains for d in s.domains):
			slides.append(s)
	return slides

def get_domains(slide_doc):
	domains_list = []
	for entry in slide_doc.domains:
		domains_list.append(entry.domain)
	return domains_list

def get_help_links(slide_doc):
	links=[]
	for link in slide_doc.help_links:
		links.append({
			'label': link.label,
			'video_id': link.video_id
		})
	return links

def get_submit_method(slide_doc):
	if slide_doc.slide_type == 'Action':
		return frappe.scrub(slide_doc.app) + '.utilities.onboarding_utils.' + slide_doc.submit_method
	return None

def get_slide_image(slide_doc):
	if slide_doc.image_src:
		return slide_doc.image_src
	return None