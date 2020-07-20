# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
# Author - Shivam Mishra <shivam@frappe.io>

from __future__ import unicode_literals
import frappe
from json import loads, dumps
from frappe import _, DoesNotExistError, ValidationError, _dict
from frappe.boot import get_allowed_pages, get_allowed_reports
from six import string_types
from functools import wraps
from frappe.cache_manager import (
	build_domain_restriced_doctype_cache,
	build_domain_restriced_page_cache,
	build_table_count_cache
)

def handle_not_exist(fn):
	@wraps(fn)
	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except DoesNotExistError:
			if frappe.message_log:
				frappe.message_log.pop()
			return []

	return wrapper


class Workspace:
	def __init__(self, page_name, minimal=False):
		self.page_name = page_name
		self.extended_cards = []
		self.extended_charts = []
		self.extended_shortcuts = []

		self.user = frappe.get_user()
		self.allowed_modules = self.get_cached('user_allowed_modules', self.get_allowed_modules)

		self.doc = self.get_page_for_user()

		if self.doc.module not in self.allowed_modules:
			raise frappe.PermissionError

		self.can_read = self.get_cached('user_perm_can_read', self.get_can_read_items)

		self.allowed_pages = get_allowed_pages(cache=True)
		self.allowed_reports = get_allowed_reports(cache=True)
		
		if not minimal:
			self.onboarding_doc = self.get_onboarding_doc()
			self.onboarding = None
		
			self.table_counts = get_table_with_counts()
		self.restricted_doctypes = frappe.cache().get_value("domain_restricted_doctypes") or build_domain_restriced_doctype_cache()
		self.restricted_pages = frappe.cache().get_value("domain_restricted_pages") or build_domain_restriced_page_cache()

	def is_page_allowed(self):
		cards = self.doc.cards + get_custom_reports_and_doctypes(self.doc.module) + self.extended_cards
		shortcuts = self.doc.shortcuts + self.extended_shortcuts
		
		for section in cards:
			links = loads(section.links) if isinstance(section.links, string_types) else section.links
			for item in links:
				if self.is_item_allowed(item.get('name'), item.get('type')):
					return True

		def _in_active_domains(item):
			if not item.restrict_to_domain:
				return True
			else:
				return item.restrict_to_domain in frappe.get_active_domains()

		for item in shortcuts:
			if self.is_item_allowed(item.link_to, item.type) and _in_active_domains(item):
				return True

		return False

	def get_cached(self, cache_key, fallback_fn):
		_cache = frappe.cache()

		value = _cache.get_value(cache_key, user=frappe.session.user)
		if value:
			return value

		value = fallback_fn()

		# Expire every six hour
		_cache.set_value(cache_key, value, frappe.session.user, 21600)
		return value

	def get_can_read_items(self):
		if not self.user.can_read:
			self.user.build_permissions()

		return self.user.can_read

	def get_allowed_modules(self):
		if not self.user.allow_modules:
			self.user.build_permissions()

		return self.user.allow_modules

	def get_page_for_user(self):
		filters = {
			'extends': self.page_name,
			'for_user': frappe.session.user
		}
		pages = frappe.get_all("Desk Page", filters=filters, limit=1)
		if pages:
			return frappe.get_cached_doc("Desk Page", pages[0])

		self.get_pages_to_extend()
		return frappe.get_cached_doc("Desk Page", self.page_name)

	def get_onboarding_doc(self):
		# Check if onboarding is enabled
		if not frappe.get_system_settings("enable_onboarding"):
			return None

		if not self.doc.onboarding:
			return None

		if frappe.db.get_value("Module Onboarding", self.doc.onboarding, "is_complete"):
			return None

		doc = frappe.get_doc("Module Onboarding", self.doc.onboarding)

		# Check if user is allowed
		allowed_roles = set(doc.get_allowed_roles())
		user_roles = set(frappe.get_roles())
		if not allowed_roles & user_roles:
			return None

		# Check if already complete
		if doc.check_completion():
			return None

		return doc

	def get_pages_to_extend(self):
		pages = frappe.get_all("Desk Page", filters={
			"extends": self.page_name,
			'restrict_to_domain': ['in', frappe.get_active_domains()],
			'for_user': '',
			'module': ['in', self.allowed_modules]
		})

		pages = [frappe.get_cached_doc("Desk Page", page['name']) for page in pages]

		for page in pages:
			self.extended_cards = self.extended_cards + page.cards
			self.extended_charts = self.extended_charts + page.charts
			self.extended_shortcuts = self.extended_shortcuts + page.shortcuts

	def is_item_allowed(self, name, item_type):
		item_type = item_type.lower()

		if item_type == "doctype":
			return (name in self.can_read and name in self.restricted_doctypes)
		if item_type == "page":
			return (name in self.allowed_pages and name in self.restricted_pages)
		if item_type == "report":
			return name in self.allowed_reports
		if item_type == "help":
			return True
		if item_type == "dashboard":
			return True

		return False

	def build_workspace(self):
		self.cards = {
			'label': _(self.doc.cards_label),
			'items': self.get_cards()
		}

		self.charts = {
			'label': _(self.doc.charts_label),
			'items': self.get_charts()
		}

		self.shortcuts = {
			'label': _(self.doc.shortcuts_label),
			'items': self.get_shortcuts()
		}

		if self.onboarding_doc:
			self.onboarding = {
				'label': _(self.onboarding_doc.title),
				'subtitle': _(self.onboarding_doc.subtitle),
				'success': _(self.onboarding_doc.success_message),
				'docs_url': self.onboarding_doc.documentation_url,
				'items': self.get_onboarding_steps()
			}
	
	@handle_not_exist
	def get_cards(self):
		cards = self.doc.cards
		if not self.doc.hide_custom:
			cards = cards + get_custom_reports_and_doctypes(self.doc.module)

		if len(self.extended_cards):
			cards = cards + self.extended_cards
		default_country = frappe.db.get_default("country")

		def _doctype_contains_a_record(name):
			exists = self.table_counts.get(name, None)
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

			# Translate label
			item["label"] = _(item.label) if item.label else _(item.name)

			return item

		new_data = []
		for section in cards:
			new_items = []
			if isinstance(section.links, string_types):
				links = loads(section.links)
			else:
				links = section.links

			for item in links:
				item = _dict(item)

				# Condition: based on country
				if item.country and item.country != default_country:
					continue

				# Check if user is allowed to view
				if self.is_item_allowed(item.name, item.type):
					prepared_item = _prepare_item(item)
					new_items.append(prepared_item)

			if new_items:
				if isinstance(section, _dict):
					new_section = section.copy()
				else:
					new_section = section.as_dict().copy()
				new_section["links"] = new_items
				new_section["label"] = _(new_section["label"])
				new_data.append(new_section)

		return new_data

	@handle_not_exist
	def get_charts(self):
		all_charts = []
		if frappe.has_permission("Dashboard Chart", throw=False):
			charts = self.doc.charts
			if len(self.extended_charts):
				charts = charts + self.extended_charts

			for chart in charts:
				if frappe.has_permission('Dashboard Chart', doc=chart.chart_name):
					# Translate label
					chart.label = _(chart.label) if chart.label else _(chart.chart_name)
					all_charts.append(chart)

		return all_charts

	@handle_not_exist
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
				if item.type == "Report":
					report = self.allowed_reports.get(item.link_to, {})
					if report.get("report_type") in ["Query Report", "Script Report"]:
						new_item['is_query_report'] = 1
					else:
						new_item['ref_doctype'] = report.get('ref_doctype')

				# Translate label
				new_item["label"] = _(item.label) if item.label else _(item.link_to)

				items.append(new_item)

		return items

	@handle_not_exist
	def get_onboarding_steps(self):
		steps = []
		for doc in self.onboarding_doc.get_steps():
			step = doc.as_dict().copy()
			step.label = _(doc.title)
			if step.action == "Create Entry":
				step.is_submittable = frappe.db.get_value("DocType", step.reference_document, 'is_submittable', cache=True)
			steps.append(step)

		return steps


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
	wspace = Workspace(page)
	wspace.build_workspace()
	return {
		'charts': wspace.charts,
		'shortcuts': wspace.shortcuts,
		'cards': wspace.cards,
		'onboarding': wspace.onboarding,
		'allow_customization': not wspace.doc.disable_user_customization
	}

@frappe.whitelist()
def get_desk_sidebar_items(flatten=False, cache=True):
	"""Get list of sidebar items for desk
	"""
	pages = []
	_cache = frappe.cache()
	if cache:
		pages = _cache.get_value("desk_sidebar_items", user=frappe.session.user)
	
	if not pages or not cache:
		# don't get domain restricted pages
		blocked_modules = frappe.get_doc('User', frappe.session.user).get_blocked_modules()

		filters = {
			'restrict_to_domain': ['in', frappe.get_active_domains()],
			'extends_another_page': 0,
			'for_user': '',
			'module': ['not in', blocked_modules]
		}

		if not frappe.local.conf.developer_mode:
			filters['developer_mode_only'] = '0'

		# pages sorted based on pinned to top and then by name
		order_by = "pin_to_top desc, pin_to_bottom asc, name asc"
		all_pages = frappe.get_all("Desk Page", fields=["name", "category"], filters=filters, order_by=order_by, ignore_permissions=True)
		pages = []
		
		# Filter Page based on Permission
		for page in all_pages:
			try:
				wspace = Workspace(page.get('name'), True)
				if wspace.is_page_allowed():
					pages.append(page)
			except frappe.PermissionError:
				pass

		_cache.set_value("desk_sidebar_items", pages, frappe.session.user)

	if flatten:
		return pages

	from collections import defaultdict
	sidebar_items = defaultdict(list)

	# The order will be maintained while categorizing
	for page in pages:
		# Translate label
		page['label'] = _(page.get('name'))
		sidebar_items[page["category"]].append(page)
	return sidebar_items

def get_table_with_counts():
	counts = frappe.cache().get_value("information_schema:counts")
	if not counts:
		counts = build_table_count_cache()

	return counts

def get_custom_reports_and_doctypes(module):
	return [
		_dict({
			"label": _("Custom Documents"),
			"links": get_custom_doctype_list(module)
		}),
		_dict({
			"label": _("Custom Reports"),
			"links": get_custom_report_list(module)
		}),
	]

def get_custom_doctype_list(module):
	doctypes =  frappe.get_all("DocType", fields=["name"], filters={"custom": 1, "istable": 0, "module": module}, order_by="name")

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
	reports =  frappe.get_all("Report", fields=["name", "ref_doctype", "report_type"], filters=
		{"is_standard": "No", "disabled": 0, "module": module},
		order_by="name")

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
	"""Get custom page from desk_page if exists or create one

	Args:
		page (stirng): Page name

	Returns:
		Object: Document object
	"""
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
	"""Save customizations as a separate doctype in Desk page per user

	Args:
		page (string): Name of the page to be edited
		config (dict): Dictionary config of al widgets

	Returns:
		Boolean: Customization saving status
	"""
	original_page = frappe.get_doc("Desk Page", page)
	page_doc = get_custom_workspace_for_user(page)

	# Update field values
	page_doc.update({
		"charts_label": original_page.charts_label,
		"cards_label": original_page.cards_label,
		"shortcuts_label": original_page.shortcuts_label,
		"module": original_page.module,
		"onboarding": original_page.onboarding,
		"developer_mode_only": original_page.developer_mode_only,
		"category": original_page.category
	})

	config = _dict(loads(config))
	if config.charts:
		page_doc.charts = prepare_widget(config.charts, "Desk Chart", "charts")
	if config.shortcuts:
		page_doc.shortcuts = prepare_widget(config.shortcuts, "Desk Shortcut", "shortcuts")
	if config.cards:
		page_doc.cards = prepare_widget(config.cards, "Desk Card", "cards")

	# Set label
	page_doc.label = page + '-' + frappe.session.user

	try:
		if page_doc.is_new():
			page_doc.insert(ignore_permissions=True)
		else:
			page_doc.save(ignore_permissions=True)
	except (ValidationError, TypeError) as e:
		# Create a json string to log
		json_config = dumps(config, sort_keys=True, indent=4)

		# Error log body
		log = \
			"""
		page: {0}
		config: {1}
		exception: {2}
		""".format(page, json_config, e)
		frappe.log_error(log, _("Could not save customization"))
		return False

	return True


def prepare_widget(config, doctype, parentfield):
	"""Create widget child table entries with parent details

	Args:
		config (dict): Dictionary containing widget config
		doctype (string): Doctype name of the child table
		parentfield (string): Parent field for the child table

	Returns:
		TYPE: List of Document objects
	"""
	if not config:
		return []
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


@frappe.whitelist()
def update_onboarding_step(name, field, value):
	"""Update status of onboaridng step

	Args:
	    name (string): Name of the doc
	    field (string): field to be updated
	    value: Value to be updated

	"""
	frappe.db.set_value("Onboarding Step", name, field, value)
