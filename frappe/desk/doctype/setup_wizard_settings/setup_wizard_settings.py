# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from erpnext.setup.doctype.setup_progress.setup_progress import get_action_completed_state
from frappe.modules import get_module_path, scrub_dt_dn
from frappe.modules.export_file import export_to_files, create_init_py

class SetupWizardSettings(Document):
	def on_update(self):
		if frappe.flags.in_import or frappe.flags.in_test:
			return

		if frappe.local.conf.get('developer_mode'):
			record_list =[['Setup Wizard Settings', self.name]]

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
		print(frappe.get_installed_apps())
		if frappe.scrub(slide_doc.app) in frappe.get_installed_apps():
			domains = get_domains(slide_doc)
			help_links = get_help_links(slide_doc)
			if slide_doc.slide_type == 'Action':
				submit_method = frappe.scrub(slide_doc.app) + '.utilities.onboarding_utils.' + slide_doc.submit_method
			else:
				submit_method = None
			if slide_doc.image_src:
				image_src = slide_doc.image_src
			else:
				image_src = None
			slides.append(frappe._dict(
				slide_type = slide_doc.slide_type,
				title = slide_doc.slide_title,
				help = slide_doc.slide_desc,
				domains = domains,
				fields = slide_doc.slide_fields,
				help_links = help_links,
				add_more = slide_doc.add_more_button,
				max_count = slide_doc.max_count,
				submit_method = submit_method,
				image_src= image_src
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
