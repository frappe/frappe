# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _, _dict
from frappe.utils.data import validate_json_string
from frappe.modules.export_file import export_to_files
from frappe.model.document import Document

from json import loads, dumps
from six import string_types

class DeskPage(Document):
	def validate(self):
		self.validate_cards_json()
		if (self.is_standard and not frappe.conf.developer_mode and not disable_saving_as_standard()):
			frappe.throw(_("You need to be in developer mode to edit this document"))

	def validate_cards_json(self):
		for card in self.cards:
			try:
				validate_json_string(card.links)
			except frappe.ValidationError:
				frappe.throw(_("Invalid JSON in card links for {0}").format(frappe.bold(card.label)))

	def on_update(self):
		if disable_saving_as_standard():
			return

		if frappe.conf.developer_mode and self.is_standard:
			export_to_files(record_list=[['Desk Page', self.name]], record_module=self.module)

	@staticmethod
	def get_module_page_map():
		filters = {
			'extends_another_page': 0,
			'for_user': '',
		}

		pages = frappe.get_all("Desk Page", fields=["name", "module"], filters=filters, as_list=1)

		return { page[1]: page[0] for page in pages if page[1] }

	def get_link_groups(self):
		cards = []
		current_card = {
			"label": "Link",
			"type": "Card Break",
			"icon": None,
			"hidden": False,
		}

		links = []
		
		for link in self.links:
			link = link.as_dict()
			
			if link.type == "Card Break":

				if links:
					current_card['links'] = links
					cards.append(current_card)
				
				current_card = link
				links = []
			
			else:
				links.append(link)

		current_card['links'] = links
		cards.append(current_card)

		return cards

	def unroll_links(self):
		link_type_map = {
			"doctype": "DocType",
			"page": "Page",
			"report": "Report",
			None: "DocType"
		}

		# Empty links table
		self.links = []

		for card in self.cards:
			if isinstance(card.links, string_types):
				links = loads(card.links)
			else:
				links = card.links

			self.append('links', {
				"label": card.label,
				"type": "Card Break",
				"icon": card.icon,
				"hidden": card.hidden or False
			})

			for link in links:
				self.append('links', {
					"label": link.get('label') or link.get('name'),
					"type": "Link",
					"link_type": link_type_map[link.get('type').lower()],
					"link_to": link.get('name'),
					"onboard": link.get('onboard'),
					"dependencies": ', '.join(link.get('dependencies', [])),
					"is_query_report": get_report_type(link.get('name')) if link.get('type').lower() == "report" else 0
				})

		self.save(ignore_permissions=True)


def disable_saving_as_standard():
	return frappe.flags.in_install or \
			frappe.flags.in_patch or \
			frappe.flags.in_test or \
			frappe.flags.in_fixtures or \
			frappe.flags.in_migrate

def rebuild_all(pages=None):
	if not pages:
		pages = frappe.get_all("Desk Page", pluck="name")
	
	failed = []
	for page in pages:
		try:
			page_doc = frappe.get_doc("Desk Page", page)
			page_doc.unroll_links()
		except Exception as e:
			print(e)
			failed.append(page)
	
	if failed:
		print(f"Rebuilding Failed for Pages: {', '.join(failed)}")


def get_report_type(report):
	report_type = frappe.get_value("Report", report, "report_type")
	return report_type in ["Query Report", "Script Report", "Custom Report"]
