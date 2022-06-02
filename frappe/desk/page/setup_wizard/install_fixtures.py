# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.global_search_settings.global_search_settings import (
	update_global_search_doctypes,
)
from frappe.utils.dashboard import sync_dashboards


def install():
	update_genders()
	update_salutations()
	update_global_search_doctypes()
	setup_email_linking()
	sync_dashboards()
	add_unsubscribe()


@frappe.whitelist()
def update_genders():
	default_genders = [
		"Male",
		"Female",
		"Other",
		"Transgender",
		"Genderqueer",
		"Non-Conforming",
		"Prefer not to say",
	]
	records = [{"doctype": "Gender", "gender": d} for d in default_genders]
	for record in records:
		frappe.get_doc(record).insert(ignore_permissions=True, ignore_if_duplicate=True)


@frappe.whitelist()
def update_salutations():
	default_salutations = ["Mr", "Ms", "Mx", "Dr", "Mrs", "Madam", "Miss", "Master", "Prof"]
	records = [{"doctype": "Salutation", "salutation": d} for d in default_salutations]
	for record in records:
		doc = frappe.new_doc(record.get("doctype"))
		doc.update(record)
		doc.insert(ignore_permissions=True, ignore_if_duplicate=True)


def setup_email_linking():
	doc = frappe.get_doc(
		{
			"doctype": "Email Account",
			"email_id": "email_linking@example.com",
		}
	)
	doc.insert(ignore_permissions=True, ignore_if_duplicate=True)


def add_unsubscribe():
	email_unsubscribe = [
		{"email": "admin@example.com", "global_unsubscribe": 1},
		{"email": "guest@example.com", "global_unsubscribe": 1},
	]

	for unsubscribe in email_unsubscribe:
		if not frappe.get_all("Email Unsubscribe", filters=unsubscribe):
			doc = frappe.new_doc("Email Unsubscribe")
			doc.update(unsubscribe)
			doc.insert(ignore_permissions=True)
