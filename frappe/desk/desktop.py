# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
# Author - Shivam Mishra <shivam@frappe.io>

from __future__ import unicode_literals
import frappe
import json
from frappe import _, DoesNotExistError
from frappe.boot import get_allowed_pages, get_allowed_reports
from frappe.cache_manager import build_table_count_cache

@frappe.whitelist()
def get_desktop_page(page):
	"""Applies permissions, customizations and returns the configruration for a page
	on desk.

	Args:
		page (string): page name

	Returns:
		dict: dictionary of cards, charts and shortcuts to be displayed on website
	"""
	try:
		doc = frappe.get_doc("Desk Page", page)
	except frappe.DoesNotExistError:
		frappe.throw(_("Desk Page {0} does not exist").format(page))

	# query = """SELECT parent from `tabDocPerm` where `role` in ({})""".format(", ".join(["%s"]*len(frappe.get_roles())))
	# standard_permissions = [item[0] for item in frappe.db.sql(query, frappe.get_roles())]

	# query = """SELECT parent from `tabCustom DocPerm` where `role` in ({})""".format(", ".join(["%s"]*len(frappe.get_roles())))
	# custom_permissions = [item[0] for item in frappe.db.sql(query, frappe.get_roles())]

	# all_permissions = standard_permissions + custom_permissions
	# print(all_permissions)

	all_cards = doc.cards + get_custom_reports_and_doctypes(doc.module)

	cards = apply_permissions(all_cards)
	# return cards
	shortcuts = prepare_shortcuts(doc.shortcuts)

	return {'charts': doc.charts, 'shortcuts': shortcuts, 'cards': cards}

def prepare_shortcuts(data):
	""" Preprocess shortcut cards (translations, keys, etc)

	Args:
		data (list): List of dictionaries containing config

	Returns:
		list: List of dictionaries containing config
	"""
	items = []
	for item in data:
		new_item = item.as_dict().copy()
		new_item['name'] = _(item.link_to)
		if ((item.type=="DocType" and item.link_to in user.can_read)
			or (item.type=="Page" and item.link_to in allowed_pages)
			or (item.type=="Report" and item.link_to in allowed_reports)
			or item.type=="help"):

			if item.type == "Page":
				page = allowed_pages[item.link_to]
				new_item['label'] = _(page.get("title", frappe.unscrub(item.link_to)))

			items.append(new_item)

	return items

def get_table_with_counts():
	counts = frappe.cache().get_value("information_schema:counts")
	if counts:
		return counts
	else:
		return build_table_count_cache()

def apply_permissions(data):
	"""Applied permissions to card to add or remove links

	Args:
		data (list): List of dicts with card data

	Returns:
		TYPE: List of dicts with card data
	"""
	default_country = frappe.db.get_default("country")

	user = frappe.get_user()
	user.build_permissions()

	allowed_pages = get_allowed_pages()
	allowed_reports = get_allowed_reports()
	exists_cache = get_table_with_counts()

	def _doctype_contains_a_record(name):
		exists = exists_cache.get(name)
		if not exists:
			if not frappe.db.get_value('DocType', name, 'issingle'):
				exists = frappe.db.count(name)
			else:
				exists = True
			exists_cache[name] = exists
		return exists

	def _get_incomplete_dependencies(name):
		return []


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
	for section in data:
		new_items = []
		if isinstance(section.links, str):
			links = json.loads(section.links)
		else:
			links = section.links

		for item in links:
			item = frappe._dict(item)

			# Condition: based on country
			if item.country and item.country!=default_country:
				continue

			# Check if user is allowed to view
			if ((item.type=="doctype" and item.name in user.can_read)
				or (item.type=="page" and item.name in allowed_pages)
				or (item.type=="report" and item.name in allowed_reports)
				or item.type=="help"):

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

@frappe.whitelist()
def get_desk_sidebar_items():
	"""Get list of sidebar items for desk
	"""
	from collections import defaultdict
	sidebar_items = defaultdict(list)
	pages = frappe.get_all("Desk Page", fields=["name", "category"], order_by="pin_to_top desc, name asc", ignore_permissions=True)
	for page in pages:
		sidebar_items[page["category"]].append(page)
	return sidebar_items

def get_custom_reports_and_doctypes(module):
	return [
		frappe._dict({
			"title": "Custom Reports",
			"links": get_report_list(module)
		}),
		frappe._dict({
			"title": "Custom DocTypes",
			"links": get_doctype_list(module)
		})
	]

def get_doctype_list(module, is_standard=False):
	doctypes =  frappe.get_list("DocType", fields=["name"], filters={"custom": 1, "istable": 0, "module": module}, order_by="name")

	out = []
	for d in doctypes:
		out.append({
			"type": "doctype",
			"name": d.name,
			"label": _(d.name)
		})

	return out


def get_report_list(module, is_standard="No"):
	"""Returns list on new style reports for modules."""
	reports =  frappe.get_list("Report", fields=["name", "ref_doctype", "report_type"], filters=
		{"is_standard": is_standard, "disabled": 0, "module": module},
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


def make_them_cards(page_name, icon="frapicon-dashboard"):
	from frappe.desk.moduleview import get

	try:
		modules = get(page_name)['data']
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
		if frappe.db.exists("Module Def", page_name):
			page.module = page_name

	for data in modules:
		# Create a New Card Child Doc
		card = frappe.new_doc("Desk Card")

		# Data clean up
		for item in data['items']:
			try:
				del item['count']
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
