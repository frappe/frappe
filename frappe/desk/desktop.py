# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
# Author - Shivam Mishra <shivam@frappe.io>

from __future__ import unicode_literals
import frappe
import json
from frappe import _, DoesNotExistError
from frappe.boot import get_allowed_pages, get_allowed_reports
from six import string_types
from frappe.cache_manager import build_domain_restriced_doctype_cache, build_domain_restriced_page_cache, build_table_count_cache

class Workspace:
	def __init__(self, page_name):
		self.page_name = page_name

	def build_cache(self):
		self.doc = frappe.get_doc("Desk Page", self.page_name)
		self.get_pages_to_extend()

		user = frappe.get_user()
		user.build_permissions()
		self.user = user

		self.allowed_pages = get_allowed_pages()
		self.allowed_reports = get_allowed_reports()

		self.table_counts = build_table_count_cache()
		self.restricted_doctypes = build_domain_restriced_doctype_cache()
		self.restricted_pages = build_domain_restriced_page_cache()

	def get_pages_to_extend(self):
		pages = frappe.get_all("Desk Page", filters={
			"extends": self.page_name,
			'restrict_to_domain': ['in', frappe.get_active_domains()]
		})

		pages = [frappe.get_doc("Desk Page", page['name']) for page in pages]
		self.extended_cards = []
		self.extended_charts = []
		self.extended_shortcuts = []

		for page in pages:
			self.extended_cards = self.extended_cards + page.cards
			self.extended_charts = self.extended_charts + page.charts
			self.extended_shortcuts = self.extended_shortcuts + page.shortcuts

	def is_item_allowed(self, name, item_type):
		item_type = item_type.lower()

		if item_type == "doctype":
			return (name in self.user.can_read and name in self.restricted_doctypes)
		if item_type == "page":
			return (name in self.allowed_pages and name in self.restricted_pages)
		if item_type == "report":
			return name in self.allowed_reports
		if item_type == "help":
			return True

		return False

	def build_workspace(self):
		self.cards = {
			'label': self.doc.cards_label,
			'items': self.get_cards()
		}

		self.charts = {
			'label': self.doc.charts_label,
			'items': self.get_charts()
		}

		self.shortcuts = {
			'label': self.doc.shortcuts_label,
			'items': self.get_shortcuts()
		}

	def get_cards(self):
		cards = self.doc.cards + get_custom_reports_and_doctypes(self.doc.module)
		if len(self.extended_cards):
			cards = cards + self.extended_cards
		default_country = frappe.db.get_default("country")

		def _doctype_contains_a_record(name):
			exists = self.table_counts.get(name)
			if not exists:
				if not frappe.db.get_value('DocType', name, 'issingle'):
					exists = frappe.db.count(name)
				else:
					exists = True
				self.table_counts[name] = exists
			return exists

		def _prepare_item(item):
			if item.dependencies:
				incomplete_dependencies = [d for d in item.dependencies if not _doctype_contains_a_record(d)]
				if len(incomplete_dependencies):
					item.incomplete_dependencies = incomplete_dependencies

			if item.onboard:
				# Mark Spotlights for initial
				if item.get("type") == "doctype":
					name = item.get("name")
					count = _doctype_contains_a_record(name)

					item["count"] = count

			return item

		new_data = []
		for section in cards:
			new_items = []
			if isinstance(section.links, string_types):
				links = json.loads(section.links)
			else:
				links = section.links

			for item in links:
				item = frappe._dict(item)

				# Condition: based on country
				if item.country and item.country != default_country:
					continue

				# Check if user is allowed to view
				if self.is_item_allowed(item.name, item.type):
					prepared_item = _prepare_item(item)
					new_items.append(item)

			if new_items:
				if isinstance(section, frappe._dict):
					new_section = section.copy()
				else:
					new_section = section.as_dict().copy()
				new_section["links"] = new_items
				new_section["label"] = section.title
				new_data.append(new_section)

		return new_data

	def get_charts(self):
		if frappe.has_permission("Dashboard Chart", throw=False):
			charts = self.doc.charts
			if len(self.extended_charts):
				charts = charts + self.extended_charts
			return [chart for chart in charts]
		return []

	def get_shortcuts(self):

		def _in_active_domains(item):
			if not item.restrict_to_domain:
				return True
			else:
				return item.restrict_to_domain in frappe.get_active_domains()

		items = []
		shortcuts = self.doc.shortcuts
		if len(self.extended_shortcuts):
			shortcuts = shortcuts + self.extended_shortcuts

		for item in shortcuts:
			new_item = item.as_dict().copy()
			new_item['name'] = _(item.link_to)
			if self.is_item_allowed(item.link_to, item.type) and _in_active_domains(item):
				if item.type == "Page":
					page = self.allowed_pages[item.link_to]
					new_item['label'] = _(page.get("title", frappe.unscrub(item.link_to)))
				if item.type == "Report":
					report = self.allowed_reports.get(item.link_to, {})
					if report.get("report_type") in ["Query Report", "Script Report"]:
						new_item['is_query_report'] = 1

				items.append(new_item)

		return items

@frappe.whitelist()
def get_desktop_page(page):
	"""Applies permissions, customizations and returns the configruration for a page
	on desk.

	Args:
		page (string): page name

	Returns:
		dict: dictionary of cards, charts and shortcuts to be displayed on website
	"""
	wspace = Workspace(page)
	try:
		wspace.build_cache()
		wspace.build_workspace()
		return {
			'charts': wspace.charts,
			'shortcuts': wspace.shortcuts,
			'cards': wspace.cards,
			'allow_customization': not wspace.doc.disable_user_customization
		}

	except DoesNotExistError:
		if frappe.message_log:
			frappe.message_log.pop()
		return None

@frappe.whitelist()
def get_desk_sidebar_items():
	"""Get list of sidebar items for desk
	"""
	# don't get domain restricted pages
	filters = {
		'restrict_to_domain': ['in', frappe.get_active_domains()],
		'extends_another_page': False
	}

	if not frappe.local.conf.developer_mode:
		filters['developer_mode_only'] = '0'

	# pages sorted based on pinned to top and then by name
	order_by = "pin_to_top desc, pin_to_bottom asc, name asc"
	pages = frappe.get_all("Desk Page", fields=["name", "category"], filters=filters, order_by=order_by, ignore_permissions=True)

	from collections import defaultdict
	sidebar_items = defaultdict(list)

	for page in pages:
		# The order will be maintained while categorizing
		sidebar_items[page["category"]].append(page)
	return sidebar_items

def get_table_with_counts():
	counts = frappe.cache().get_value("information_schema:counts")
	if not counts:
		counts = build_table_count_cache()

	return counts

def get_custom_reports_and_doctypes(module):
	return [
		frappe._dict({
			"title": "Custom",
			"links": get_custom_doctype_list(module) + get_custom_report_list(module)
		})
	]

def get_custom_doctype_list(module):
	doctypes =  frappe.get_list("DocType", fields=["name"], filters={"custom": 1, "istable": 0, "module": module}, order_by="name", ignore_permissions=True)

	out = []
	for d in doctypes:
		out.append({
			"type": "doctype",
			"name": d.name,
			"label": _(d.name)
		})

	return out


def get_custom_report_list(module):
	"""Returns list on new style reports for modules."""
	reports =  frappe.get_list("Report", fields=["name", "ref_doctype", "report_type"], filters=
		{"is_standard": "No", "disabled": 0, "module": module},
		order_by="name", ignore_permissions=True)

	out = []
	for r in reports:
		out.append({
			"type": "report",
			"doctype": r.ref_doctype,
			"is_query_report": 1 if r.report_type in ("Query Report", "Script Report", "Custom Report") else 0,
			"label": _(r.name),
			"name": r.name
		})

	return out

def make_them_pages():
	"""Helper function to make pages
	"""
	pages = [
				('Desk', 'frappe', 'octicon octicon-calendar'),
				('Settings', 'frappe', 'octicon octicon-settings'),
				('Users and Permissions', 'frappe', 'octicon octicon-settings'),
				('Customization', 'frappe', 'octicon octicon-settings'),
				('Integrations', 'frappe', 'octicon octicon-globe'),
				('Core', 'frappe', 'octicon octicon-circuit-board'),
				('Website', 'frappe', 'octicon octicon-globe'),
				('Getting Started', 'erpnext', 'fa fa-check-square-o'),
				('Accounts', 'erpnext', 'octicon octicon-repo'),
				('Selling', 'erpnext', 'octicon octicon-tag'),
				('Buying', 'erpnext', 'octicon octicon-briefcase'),
				('Stock', 'erpnext', 'octicon octicon-package'),
				('Assets', 'erpnext', 'octicon octicon-database'),
				('Projects', 'erpnext', 'octicon octicon-rocket'),
				('CRM', 'erpnext', 'octicon octicon-broadcast'),
				('Support', 'erpnext', 'fa fa-check-square-o'),
				('HR', 'erpnext', 'octicon octicon-organization'),
				('Quality Management', 'erpnext', 'fa fa-check-square-o'),
				('Manufacturing', 'erpnext', 'octicon octicon-tools'),
				('Retail', 'erpnext', 'octicon octicon-credit-card'),
				('Education', 'erpnext', 'octicon octicon-mortar-board'),
				('Healthcare', 'erpnext', 'fa fa-heartbeat'),
				('Agriculture', 'erpnext', 'octicon octicon-globe'),
				('Non Profit', 'erpnext', 'octicon octicon-heart'),
				('Help', 'erpnext', 'octicon octicon-device-camera-video')
			]

	for page in pages:
		print("Processing Page: {0}".format(page[0]))
		make_them_cards(page[0], page[2])


def make_them_cards(page_name, from_module=None, to_module=None, icon=None):
	from frappe.desk.moduleview import get

	if not from_module:
		from_module = page_name

	if not to_module:
		to_module = page_name

	try:
		modules = get(from_module)['data']
	except:
		return

	# Find or make page doc
	if frappe.db.exists("Desk Page", page_name):
		page = frappe.get_doc("Desk Page", page_name)
		print("--- Got Page: {0}".format(page.name))
	else:
		page = frappe.new_doc("Desk Page")
		page.label = page_name
		page.cards = []
		page.icon = icon
		print("--- New Page: {0}".format(page.name))

		# Guess Which Module
		if not to_module and frappe.db.exists("Module Def", page_name):
			page.module = page_name

		if to_module:
			page.module = to_module
		elif frappe.db.exists("Module Def", page_name):
			page.module = page_name

	for data in modules:
		# Create a New Card Child Doc
		card = frappe.new_doc("Desk Card")

		# Data clean up
		for item in data['items']:
			try:
				del item['count']
				del item['incomplete_dependencies']
			except KeyError:
				pass

		# Set Child doc values
		card.title = data['label']
		card.icon = data.get('icon')
		# Pretty dump JSON
		card.links = json.dumps(data['items'], indent=4, sort_keys=True)

		# Set Parent attributes
		card.parent = page.name
		card.parenttype = page.doctype
		card.parentfield = "cards"

		# Add cards to page doc
		print("------- Adding Card: {0}".format(card.title))
		page.cards.append(card)

	# End it all
	page.save()
	frappe.db.commit()
	return