# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import N_
from frappe.deprecation_dumpster import _
from frappe.desk.doctype.global_search_settings.global_search_settings import (
	update_global_search_doctypes,
)
from frappe.utils.dashboard import sync_dashboards


def install():
	update_genders()
	update_salutations()
	update_global_search_doctypes()
	sync_dashboards()


def update_genders():
	for gender in (
		N_("Male"),
		N_("Female"),
		N_("Other"),
		N_("Transgender"),
		N_("Genderqueer"),
		N_("Non-Conforming"),
		N_("Prefer not to say"),
	):
		doc = frappe.new_doc("Gender")
		doc.gender = gender
		doc.insert(ignore_permissions=True, ignore_if_duplicate=True)


def update_salutations():
	for salutation in (
		N_("Mr"),
		N_("Ms"),
		N_("Mx"),
		N_("Dr"),
		N_("Mrs"),
		N_("Madam"),
		N_("Miss"),
		N_("Master"),
		N_("Prof"),
	):
		doc = frappe.new_doc("Salutation")
		doc.salutation = salutation
		doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
