# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.core.doctype.data_import.data_import import import_doc
from frappe.desk.doctype.global_search_settings.global_search_settings import (
	update_global_search_doctypes,
)
from frappe.utils.dashboard import sync_dashboards


def _(x, *args, **kwargs):
	"""Redefine the translation function to return the string as is.
	We want to create english records but still mark the strings as translatable.
	The respective DocTypes have 'Translate Link Fields' enabled."""
	return x


def install():
	update_genders()
	update_salutations()
	update_global_search_doctypes()
	update_marketing_sources()
	update_marketing_medium()
	setup_email_linking()
	sync_dashboards()
	add_unsubscribe()


def update_genders():
	for gender in (
		_("Male"),
		_("Female"),
		_("Other"),
		_("Transgender"),
		_("Genderqueer"),
		_("Non-Conforming"),
		_("Prefer not to say"),
	):
		doc = frappe.new_doc("Gender")
		doc.gender = gender
		doc.insert(ignore_permissions=True, ignore_if_duplicate=True)


def update_salutations():
	for salutation in (
		_("Mr"),
		_("Ms"),
		_("Mx"),
		_("Dr"),
		_("Mrs"),
		_("Madam"),
		_("Miss"),
		_("Master"),
		_("Prof"),
	):
		doc = frappe.new_doc("Salutation")
		doc.salutation = salutation
		doc.insert(ignore_permissions=True, ignore_if_duplicate=True)


def update_marketing_sources():
	file_path = frappe.get_app_path("frappe", "desk", "page", "setup_wizard", "marketing_source.json")
	import_doc(file_path)


def update_marketing_medium():
	file_path = frappe.get_app_path("frappe", "desk", "page", "setup_wizard", "marketing_medium.json")
	import_doc(file_path)


def setup_email_linking():
	doc = frappe.new_doc("Email Account")
	doc.email_id = "email_linking@example.com"
	doc.insert(ignore_permissions=True, ignore_if_duplicate=True)


def add_unsubscribe():
	for unsubscribe in [
		{"email": "admin@example.com", "global_unsubscribe": 1},
		{"email": "guest@example.com", "global_unsubscribe": 1},
	]:
		if not frappe.get_all("Email Unsubscribe", filters=unsubscribe):
			doc = frappe.new_doc("Email Unsubscribe")
			doc.update(unsubscribe)
			doc.insert(ignore_permissions=True)
