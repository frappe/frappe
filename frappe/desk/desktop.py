"""Summary
"""
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
# Author - Shivam Mishra <shivam@frappe.io>

from __future__ import unicode_literals
import frappe
import json
from frappe import _, DoesNotExistError
from frappe.boot import get_allowed_pages, get_allowed_reports

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

	cards = apply_permissions(doc.cards)
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
		items.append(new_item)

	return items

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

	new_data = []
	for section in data:
		new_items = []
		links = json.loads(section.links)
		for item in links:
			item = frappe._dict(item)

			if item.country and item.country!=default_country:
				continue

			if ((item.type=="doctype" and item.name in user.can_read)
				or (item.type=="page" and item.name in allowed_pages)
				or (item.type=="report" and item.name in allowed_reports)
				or item.type=="help"):

				new_items.append(item)

		if new_items:
			new_section = section.as_dict().copy()
			new_section["links"] = new_items
			new_section["label"] = section.title
			new_data.append(new_section)

	return new_data

@frappe.whitelist()
def get_desk_sidebar_items():
	"""Get list of sidebar items for desk
	"""
	pages = [frappe.get_doc("Desk Page", item['name']) for item in frappe.get_all("Desk Page", order_by="name")]
	return pages

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
