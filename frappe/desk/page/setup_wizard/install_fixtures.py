# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _noop
from frappe.desk.doctype.global_search_settings.global_search_settings import (
	update_global_search_doctypes,
)
from frappe.utils.dashboard import sync_dashboards


def install():
	update_genders()
	update_salutations()
	update_global_search_doctypes()
	sync_dashboards()
	add_unsubscribe()


def update_genders():
	for gender in (
		_noop("Male"),
		_noop("Female"),
		_noop("Other"),
		_noop("Transgender"),
		_noop("Genderqueer"),
		_noop("Non-Conforming"),
		_noop("Prefer not to say"),
	):
		doc = frappe.new_doc("Gender")
		doc.gender = gender
		doc.insert(ignore_permissions=True, ignore_if_duplicate=True)


def update_salutations():
	for salutation in (
		_noop("Mr"),
		_noop("Ms"),
		_noop("Mx"),
		_noop("Dr"),
		_noop("Mrs"),
		_noop("Madam"),
		_noop("Miss"),
		_noop("Master"),
		_noop("Prof"),
	):
		doc = frappe.new_doc("Salutation")
		doc.salutation = salutation
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
