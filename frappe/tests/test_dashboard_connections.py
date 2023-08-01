# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
from unittest.mock import patch

import frappe
import frappe.utils
from frappe.desk.notifications import get_open_count
from frappe.tests.utils import FrappeTestCase


class TestDashboardConnections(FrappeTestCase):
	@patch.dict(frappe.conf, {"developer_mode": 1})
	def setUp(self):
		delete_test_data()
		create_test_data()

	@patch.dict(frappe.conf, {"developer_mode": 1})
	def tearDown(self):
		delete_test_data()

	def test_internal_link_count(self):
		earth = frappe.get_doc(
			{
				"doctype": "Doctype B With Child Table With Link To Doctype A",
				"title": "Earth",
			}
		)
		earth.append(
			"child_table",
			{
				"title": "Earth",
			},
		)
		earth.insert()

		mars = frappe.get_doc(
			{
				"doctype": "Doctype A With Child Table With Link To Doctype B",
				"title": "Mars",
			}
		)
		mars.append(
			"child_table",
			{"title": "Mars", "doctype_b_with_child_table_with_link_to_doctype_a": "Earth"},
		)
		mars.insert()

		expected_open_count = {
			"count": {
				"external_links_found": [],
				"internal_links_found": [
					{
						"count": 1,
						"doctype": "Doctype B With Child Table With Link To Doctype A",
						"names": ["Earth"],
						"open_count": 0,
					}
				],
			}
		}

		with patch.object(
			mars.meta,
			"get_dashboard_data",
			return_value=get_dashboard_for_doctype_a_with_child_table_with_link_to_doctype_b(),
		):
			self.assertEqual(
				get_open_count("Doctype A With Child Table With Link To Doctype B", "Mars"),
				expected_open_count,
			)

	def test_external_link_count(self):
		saturn = frappe.get_doc(
			{
				"doctype": "Doctype A With Child Table With Link To Doctype B",
				"title": "Saturn",
			}
		)
		saturn.append(
			"child_table",
			{
				"title": "Saturn",
			},
		)
		saturn.insert()

		pluto = frappe.get_doc(
			{
				"doctype": "Doctype B With Child Table With Link To Doctype A",
				"title": "Pluto",
			}
		)
		pluto.append(
			"child_table",
			{"title": "Pluto", "doctype_a_with_child_table_with_link_to_doctype_b": "Saturn"},
		)
		pluto.insert()

		expected_open_count = {
			"count": {
				"external_links_found": [
					{"doctype": "Doctype B With Child Table With Link To Doctype A", "open_count": 0, "count": 1}
				],
				"internal_links_found": [],
			}
		}

		with patch.object(
			saturn.meta,
			"get_dashboard_data",
			return_value=get_dashboard_for_doctype_a_with_child_table_with_link_to_doctype_b(),
		):
			self.assertEqual(
				get_open_count("Doctype A With Child Table With Link To Doctype B", "Saturn"),
				expected_open_count,
			)


def create_test_data():
	create_child_table_with_link_to_doctype_a()
	create_child_table_with_link_to_doctype_b()
	create_doctype_a_with_child_table_with_link_to_doctype_b()
	create_doctype_b_with_child_table_with_link_to_doctype_a()
	add_links_in_child_tables()


def delete_test_data():
	doctypes = [
		"Child Table With Link To Doctype A",
		"Child Table With Link To Doctype B",
		"Doctype A With Child Table With Link To Doctype B",
		"Doctype B With Child Table With Link To Doctype A",
	]
	for doctype in doctypes:
		if frappe.db.table_exists(doctype):
			frappe.db.delete(doctype)
			frappe.delete_doc("DocType", doctype, force=True)


def create_child_table_with_link_to_doctype_a():
	frappe.get_doc(
		{
			"doctype": "DocType",
			"name": "Child Table With Link To Doctype A",
			"module": "Custom",
			"autoname": "field:title",
			"fields": [
				{"fieldname": "title", "fieldtype": "Data", "label": "Title", "reqd": 1, "unique": 1}
			],
			"istable": 1,
			"naming_rule": "By fieldname",
			"permissions": [{"role": "System Manager"}],
		}
	).insert(ignore_if_duplicate=True)


def create_child_table_with_link_to_doctype_b():
	frappe.get_doc(
		{
			"doctype": "DocType",
			"name": "Child Table With Link To Doctype B",
			"module": "Custom",
			"autoname": "field:title",
			"fields": [
				{"fieldname": "title", "fieldtype": "Data", "label": "Title", "reqd": 1, "unique": 1}
			],
			"istable": 1,
			"naming_rule": "By fieldname",
			"permissions": [{"role": "System Manager"}],
		}
	).insert(ignore_if_duplicate=True)


def add_links_in_child_tables():
	child_table_with_link_to_doctype_a = frappe.get_doc(
		"DocType", "Child Table With Link To Doctype A"
	)
	if len(child_table_with_link_to_doctype_a.fields) == 1:
		child_table_with_link_to_doctype_a.append(
			"fields",
			{
				"fieldname": "doctype_a_with_child_table_with_link_to_doctype_b",
				"fieldtype": "Link",
				"in_list_view": 1,
				"label": "Doctype A With Child Table With Link To Doctype B" or "Doctype to Link",
				"options": "Doctype A With Child Table With Link To Doctype B" or "Doctype to Link",
			},
		)
		child_table_with_link_to_doctype_a.save()

	child_table_with_link_to_doctype_b = frappe.get_doc(
		"DocType", "Child Table With Link To Doctype B"
	)
	if len(child_table_with_link_to_doctype_b.fields) == 1:
		child_table_with_link_to_doctype_b.append(
			"fields",
			{
				"fieldname": "doctype_b_with_child_table_with_link_to_doctype_a",
				"fieldtype": "Link",
				"in_list_view": 1,
				"label": "Doctype B With Child Table With Link To Doctype A" or "Doctype to Link",
				"options": "Doctype B With Child Table With Link To Doctype A" or "Doctype to Link",
			},
		)
		child_table_with_link_to_doctype_b.save()


def create_doctype_a_with_child_table_with_link_to_doctype_b():
	frappe.get_doc(
		{
			"doctype": "DocType",
			"name": "Doctype A With Child Table With Link To Doctype B",
			"module": "Custom",
			"autoname": "field:title",
			"fields": [
				{"fieldname": "title", "fieldtype": "Data", "label": "Title", "unique": 1},
				{
					"fieldname": "child_table",
					"fieldtype": "Table",
					"label": "Child Table",
					"options": "Child Table With Link To Doctype B",
				},
				{
					"fieldname": "connections_tab",
					"fieldtype": "Tab Break",
					"label": "Connections",
					"show_dashboard": 1,
				},
			],
			"naming_rule": "By fieldname",
			"permissions": [{"role": "System Manager"}],
		}
	).insert(ignore_if_duplicate=True)


def create_doctype_b_with_child_table_with_link_to_doctype_a():
	frappe.get_doc(
		{
			"doctype": "DocType",
			"name": "Doctype B With Child Table With Link To Doctype A",
			"module": "Custom",
			"autoname": "field:title",
			"fields": [
				{"fieldname": "title", "fieldtype": "Data", "label": "Title", "unique": 1},
				{
					"fieldname": "child_table",
					"fieldtype": "Table",
					"label": "Child Table",
					"options": "Child Table With Link To Doctype A",
				},
				{
					"fieldname": "connections_tab",
					"fieldtype": "Tab Break",
					"label": "Connections",
					"show_dashboard": 1,
				},
			],
			"naming_rule": "By fieldname",
			"permissions": [{"role": "System Manager"}],
		}
	).insert(ignore_if_duplicate=True)


def get_dashboard_for_doctype_a_with_child_table_with_link_to_doctype_b():
	dashboard = frappe._dict()

	data = {
		"fieldname": "doctype_a_with_child_table_with_link_to_doctype_b",
		"internal_links": {
			"Doctype B With Child Table With Link To Doctype A": [
				"child_table",
				"doctype_b_with_child_table_with_link_to_doctype_a",
			],
		},
		"transactions": [
			{"label": "Reference", "items": ["Doctype B With Child Table With Link To Doctype A"]},
		],
	}

	dashboard.fieldname = data["fieldname"]
	dashboard.internal_links = data["internal_links"]
	dashboard.transactions = data["transactions"]

	return dashboard
