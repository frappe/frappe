# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
# Author - Shivam Mishra <shivam@frappe.io>

from __future__ import unicode_literals
import frappe
from json import loads
from frappe import _, DoesNotExistError
from frappe.boot import get_allowed_pages, get_allowed_reports
from six import string_types
from frappe.cache_manager import build_domain_restriced_doctype_cache, build_domain_restriced_page_cache, build_table_count_cache

class Workspace:
	def __init__(self, page_name):
		self.page_name = page_name
		self.extended_cards = []
		self.extended_charts = []
		self.extended_shortcuts = []

		user = frappe.get_user()
		user.build_permissions()

		self.blocked_modules = frappe.get_doc('User', frappe.session.user).get_blocked_modules()
		self.doc = self.get_page_for_user()

		if self.doc.module in self.blocked_modules:
			raise frappe.PermissionError

		self.user = user
		self.allowed_pages = get_allowed_pages()
		self.allowed_reports = get_allowed_reports()

		self.table_counts = get_table_with_counts()
		self.restricted_doctypes = build_domain_restriced_doctype_cache()
		self.restricted_pages = build_domain_restriced_page_cache()

	def get_page_for_user(self):
		filters = {
			'extends': self.page_name,
			'for_user': frappe.session.user
		}
		pages = frappe.get_list("Desk Page", filters=filters)
		if pages:
			return frappe.get_doc("Desk Page", pages[0])

		self.get_pages_to_extend()
		return frappe.get_doc("Desk Page", self.page_name)

	def get_pages_to_extend(self):
		pages = frappe.get_all("Desk Page", filters={
			"extends": self.page_name,
			'restrict_to_domain': ['in', frappe.get_active_domains()],
			'for_user': '',
			'module': ['not in', self.blocked_modules]
		})

		pages = [frappe.get_doc("Desk Page", page['name']) for page in pages]

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
				links = loads(section.links)
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
				new_data.append(new_section)

		return new_data

	def get_charts(self):
		all_charts = []
		if frappe.has_permission("Dashboard Chart", throw=False):
			charts = self.doc.charts
			if len(self.extended_charts):
				charts = charts + self.extended_charts

			for chart in charts:
				if frappe.has_permission('Dashboard Chart', doc=chart.chart_name):
					chart.label = chart.label if chart.label else chart.chart_name
					all_charts.append(chart)

		return all_charts

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
@frappe.read_only()
def get_desktop_page(page):
	"""Applies permissions, customizations and returns the configruration for a page
	on desk.

	Args:
		page (string): page name

	Returns:
		dict: dictionary of cards, charts and shortcuts to be displayed on website
	"""
	try:
		wspace = Workspace(page)
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
	blocked_modules = frappe.get_doc('User', frappe.session.user).get_blocked_modules()

	filters = {
		'restrict_to_domain': ['in', frappe.get_active_domains()],
		'extends_another_page': 0,
		'is_standard': 1,
		'for_user': '',
		'module': ['not in', blocked_modules]
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
			"label": "Custom",
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

def get_custom_workspace_for_user(page):
	filters = {
		'extends': page,
		'for_user': frappe.session.user
	}
	pages = frappe.get_list("Desk Page", filters=filters)
	if pages:
		return frappe.get_doc("Desk Page", pages[0])
	doc = frappe.new_doc("Desk Page")
	doc.extends = page
	doc.for_user = frappe.session.user
	return doc


@frappe.whitelist()
def save_customization(page, config):
	original_page = frappe.get_doc("Desk Page", page)
	page_doc = get_custom_workspace_for_user(page)

	# Update field values
	page_doc.update({
		"charts_label": original_page.charts_label,
		"cards_label": original_page.cards_label,
		"shortcuts_label": original_page.shortcuts_label,
		"icon": original_page.icon,
		"module": original_page.module,
		"developer_mode_only": original_page.developer_mode_only,
		"category": original_page.category
	})

	config = frappe._dict(loads(config))
	page_doc.charts = prepare_widget(config.charts, "Desk Chart", "charts")
	page_doc.shortcuts = prepare_widget(config.shortcuts, "Desk Shortcut", "shortcuts")
	page_doc.cards = prepare_widget(config.cards, "Desk Card", "cards")

	# Set label
	page_doc.label = page + '-' + frappe.session.user

	if page_doc.is_new():
		page_doc.insert(ignore_permissions=True)
	else:
		page_doc.save(ignore_permissions=True)

def prepare_widget(config, doctype, parentfield):
	if not config:
		return
	order = config.get('order')
	widgets = config.get('widgets')
	prepare_widget_list = []
	for idx, name in enumerate(order):
		wid_config = widgets[name].copy()
		# Some cleanup
		wid_config.pop("name", None)

		# New Doc
		doc = frappe.new_doc(doctype)
		doc.update(wid_config)

		# Manually Set IDX
		doc.idx = idx + 1

		# Set Parent Field
		doc.parentfield = parentfield

		prepare_widget_list.append(doc)
	return prepare_widget_list
