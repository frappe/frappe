# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.modules.export_file import export_to_files
from frappe.model.document import Document
from frappe.desk.utils import validate_route_conflict

from json import loads

class Workspace(Document):
	def validate(self):
		if (self.is_standard and not frappe.conf.developer_mode and not disable_saving_as_standard()):
			frappe.throw(_("You need to be in developer mode to edit this document"))
		validate_route_conflict(self.doctype, self.name)

		duplicate_exists = frappe.db.exists("Workspace", {
			"name": ["!=", self.name], 'is_default': 1, 'extends': self.extends
		})

		if self.is_default and self.name and duplicate_exists:
			frappe.throw(_("You can only have one default page that extends a particular standard page."))

	def on_update(self):
		if disable_saving_as_standard():
			return

		if frappe.conf.developer_mode and self.is_standard:
			export_to_files(record_list=[['Workspace', self.name]], record_module=self.module)

	@staticmethod
	def get_module_page_map():
		filters = {
			'extends_another_page': 0,
			'for_user': '',
		}

		pages = frappe.get_all("Workspace", fields=["name", "module"], filters=filters, as_list=1)

		return { page[1]: page[0] for page in pages if page[1] }

	def get_link_groups(self):
		cards = []
		current_card = frappe._dict({
			"label": "Link",
			"type": "Card Break",
			"icon": None,
			"hidden": False,
		})

		card_links = []

		for link in self.links:
			link = link.as_dict()
			if link.type == "Card Break":
				if card_links and (not current_card.only_for or current_card.only_for == frappe.get_system_settings('country')):
					current_card['links'] = card_links
					cards.append(current_card)

				current_card = link
				card_links = []
			else:
				card_links.append(link)

		current_card['links'] = card_links
		cards.append(current_card)

		return cards

	def build_links_table_from_cards(self, config):
		# Empty links table
		self.links = []
		order = config.get('order')
		widgets = config.get('widgets')

		for idx, name in enumerate(order):
			card = widgets[name].copy()
			links = loads(card.get('links'))

			self.append('links', {
				"label": card.get('label'),
				"type": "Card Break",
				"icon": card.get('icon'),
				"hidden": card.get('hidden') or False
			})

			for link in links:
				self.append('links', {
					"label": link.get('label'),
					"type": "Link",
					"link_type": link.get('link_type'),
					"link_to": link.get('link_to'),
					"onboard": link.get('onboard'),
					"only_for": link.get('only_for'),
					"dependencies": link.get('dependencies'),
					"is_query_report": link.get('is_query_report')
				})


def disable_saving_as_standard():
	return frappe.flags.in_install or \
			frappe.flags.in_patch or \
			frappe.flags.in_test or \
			frappe.flags.in_fixtures or \
			frappe.flags.in_migrate

def get_link_type(key):
	key = key.lower()

	link_type_map = {
		"doctype": "DocType",
		"page": "Page",
		"report": "Report"
	}

	if key in link_type_map:
		return link_type_map[key]

	return "DocType"

def get_report_type(report):
	report_type = frappe.get_value("Report", report, "report_type")
	return report_type in ["Query Report", "Script Report", "Custom Report"]
