# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
from unittest.mock import patch

import frappe
import frappe.utils
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.custom.doctype.customize_form.test_customize_form import TestCustomizeForm
from frappe.desk.notifications import get_open_count
from frappe.tests import IntegrationTestCase


class TestDashboardConnections(IntegrationTestCase):
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
				"doctype": "Test Doctype B With Child Table With Link To Doctype A",
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
				"doctype": "Test Doctype A With Child Table With Link To Doctype B",
				"title": "Mars",
			}
		)
		mars.append(
			"child_table",
			{"title": "Mars", "test_doctype_b_with_test_child_table_with_link_to_doctype_a": "Earth"},
		)
		mars.insert()

		expected_open_count = {
			"count": {
				"external_links_found": [],
				"internal_links_found": [
					{
						"count": 1,
						"doctype": "Test Doctype B With Child Table With Link To Doctype A",
						"names": ["Earth"],
						"open_count": 0,
					}
				],
			}
		}

		with patch.object(
			mars.meta,
			"get_dashboard_data",
			return_value=get_dashboard_for_test_doctype_a_with_test_child_table_with_link_to_doctype_b(),
		):
			self.assertEqual(
				get_open_count("Test Doctype A With Child Table With Link To Doctype B", "Mars"),
				expected_open_count,
			)

	def test_external_link_count(self):
		saturn = frappe.get_doc(
			{
				"doctype": "Test Doctype A With Child Table With Link To Doctype B",
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
				"doctype": "Test Doctype B With Child Table With Link To Doctype A",
				"title": "Pluto",
			}
		)
		pluto.append(
			"child_table",
			{"title": "Pluto", "test_doctype_a_with_test_child_table_with_link_to_doctype_b": "Saturn"},
		)
		pluto.insert()

		expected_open_count = {
			"count": {
				"external_links_found": [
					{
						"doctype": "Test Doctype B With Child Table With Link To Doctype A",
						"open_count": 0,
						"count": 1,
					}
				],
				"internal_links_found": [],
			}
		}

		with patch.object(
			saturn.meta,
			"get_dashboard_data",
			return_value=get_dashboard_for_test_doctype_a_with_test_child_table_with_link_to_doctype_b(),
		):
			self.assertEqual(
				get_open_count("Test Doctype A With Child Table With Link To Doctype B", "Saturn"),
				expected_open_count,
			)

	def test_external_link_count_with_shared_link_field_in_child_tables(self):
		jupiter = frappe.get_doc(
			doctype="Test Doctype A With Child Table With Link To Doctype B", title="Jupiter"
		).insert()

		voyager = frappe.get_doc(doctype="Test Doctype C With Duplicate Link To Doctype A", title="Voyager")
		voyager.append(
			"child_table",
			{
				"title": "Voyager",
				"test_doctype_a_with_test_child_table_with_link_to_doctype_b": "Jupiter",
			},
		)
		voyager.insert()

		dashboard = frappe._dict(
			fieldname="test_doctype_a_with_test_child_table_with_link_to_doctype_b",
			transactions=[
				{"label": "Reference", "items": ["Test Doctype C With Duplicate Link To Doctype A"]}
			],
		)

		with patch.object(jupiter.meta, "get_dashboard_data", return_value=dashboard):
			connections = get_open_count("Test Doctype A With Child Table With Link To Doctype B", "Jupiter")[
				"count"
			]

		self.assertEqual(
			connections["external_links_found"],
			[
				{
					"doctype": "Test Doctype C With Duplicate Link To Doctype A",
					"open_count": 0,
					"count": 1,
					"names": ["Voyager"],
				}
			],
		)

	def test_internal_link_without_external_field_reports_zero(self):
		venus = frappe.get_doc(
			{
				"doctype": "Test Doctype A With Child Table With Link To Doctype B",
				"title": "Venus",
			}
		)
		venus.append("child_table", {"title": "Venus"})
		venus.insert()

		# internal link with no rows falls back to an external-link probe; the
		# fieldname doesn't exist on the target doctype, so no query should run
		dashboard = get_dashboard_for_test_doctype_a_with_test_child_table_with_link_to_doctype_b()
		dashboard.fieldname = "nonexistent_column"

		expected_open_count = {
			"count": {
				"external_links_found": [
					{
						"doctype": "Test Doctype B With Child Table With Link To Doctype A",
						"open_count": 0,
						"count": 0,
					}
				],
				"internal_links_found": [],
			}
		}

		with patch.object(venus.meta, "get_dashboard_data", return_value=dashboard):
			self.assertEqual(
				get_open_count("Test Doctype A With Child Table With Link To Doctype B", "Venus"),
				expected_open_count,
			)

	def test_external_doctype_link_with_dashboard_override(self):
		# add a custom links
		todo = TestCustomizeForm().get_customize_form("ToDo")
		todo.append("links", dict(link_doctype="Test Doctype D", link_fieldname="doclink", group="Test"))
		todo.append("links", dict(link_doctype="Test Doctype E", link_fieldname="todo", group="Test"))
		todo.run_method("save_customization")

		# create a test doc
		todo_doc = frappe.get_doc(doctype="ToDo", description="test").insert()
		frappe.get_doc(doctype="Test Doctype D", title="d-001", doclink=todo_doc.name).insert()
		frappe.get_doc(doctype="Test Doctype E", title="e-001", todo=todo_doc.name).insert()

		connections = get_open_count("ToDo", todo_doc.name)["count"]
		self.assertEqual(len(connections["external_links_found"]), 2)

		# Change standard fieldname, see if all custom links still work
		with self.patch_hooks(
			{
				"override_doctype_dashboards": {
					"ToDo": ["frappe.tests.test_dashboard_connections.get_dashboard_for_todo"]
				}
			}
		):
			connections = get_open_count("ToDo", todo_doc.name)["count"]
			self.assertEqual(len(connections["external_links_found"]), 2)

		# remove the custom links
		todo = TestCustomizeForm().get_customize_form("ToDo")
		todo.links = todo.links[:-2]
		todo.run_method("save_customization")


def create_test_data():
	create_test_child_table_with_link_to_doctype_a()
	create_test_child_table_with_link_to_doctype_b()
	create_test_doctype_a_with_test_child_table_with_link_to_doctype_b()
	create_test_doctype_b_with_test_child_table_with_link_to_doctype_a()
	create_linked_doctypes()
	add_links_in_child_tables()
	create_test_doctype_c_with_duplicate_link_to_doctype_a()


def delete_test_data():
	doctypes = [
		"Test Child Table With Link To Doctype A",
		"Test Child Table With Link To Doctype B",
		"Test Doctype A With Child Table With Link To Doctype B",
		"Test Doctype B With Child Table With Link To Doctype A",
		"Test Doctype D",
		"Test Doctype E",
		"Test Doctype C With Duplicate Link To Doctype A",
		"Test Unrelated Child Table With Link To Doctype A",
	]
	for doctype in doctypes:
		if frappe.db.table_exists(doctype):
			frappe.db.delete(doctype)
			frappe.delete_doc("DocType", doctype, force=True)


def create_test_child_table_with_link_to_doctype_a():
	new_doctype(
		"Test Child Table With Link To Doctype A",
		istable=1,
		fields=[{"fieldname": "title", "fieldtype": "Data", "label": "Title", "reqd": 1, "unique": 1}],
		custom=False,
		autoname="field:title",
		naming_rule="By fieldname",
	).insert(ignore_if_duplicate=True)


def create_test_child_table_with_link_to_doctype_b():
	new_doctype(
		"Test Child Table With Link To Doctype B",
		istable=1,
		fields=[{"fieldname": "title", "fieldtype": "Data", "label": "Title", "reqd": 1, "unique": 1}],
		custom=False,
		autoname="field:title",
		naming_rule="By fieldname",
	).insert(ignore_if_duplicate=True)


def add_links_in_child_tables():
	test_child_table_with_link_to_doctype_a = frappe.get_doc(
		"DocType", "Test Child Table With Link To Doctype A"
	)
	if len(test_child_table_with_link_to_doctype_a.fields) == 1:
		test_child_table_with_link_to_doctype_a.append(
			"fields",
			{
				"fieldname": "test_doctype_a_with_test_child_table_with_link_to_doctype_b",
				"fieldtype": "Link",
				"in_list_view": 1,
				"label": "Test Doctype A With Child Table With Link To Doctype B" or "Doctype to Link",
				"options": "Test Doctype A With Child Table With Link To Doctype B" or "Doctype to Link",
			},
		)
		test_child_table_with_link_to_doctype_a.save()

	test_child_table_with_link_to_doctype_b = frappe.get_doc(
		"DocType", "Test Child Table With Link To Doctype B"
	)
	if len(test_child_table_with_link_to_doctype_b.fields) == 1:
		test_child_table_with_link_to_doctype_b.append(
			"fields",
			{
				"fieldname": "test_doctype_b_with_test_child_table_with_link_to_doctype_a",
				"fieldtype": "Link",
				"in_list_view": 1,
				"label": "Test Doctype B With Child Table With Link To Doctype A" or "Doctype to Link",
				"options": "Test Doctype B With Child Table With Link To Doctype A" or "Doctype to Link",
			},
		)
		test_child_table_with_link_to_doctype_b.save()


def create_test_doctype_a_with_test_child_table_with_link_to_doctype_b():
	new_doctype(
		"Test Doctype A With Child Table With Link To Doctype B",
		fields=[
			{"fieldname": "title", "fieldtype": "Data", "label": "Title", "unique": 1},
			{
				"fieldname": "child_table",
				"fieldtype": "Table",
				"label": "Child Table",
				"options": "Test Child Table With Link To Doctype B",
			},
			{
				"fieldname": "connections_tab",
				"fieldtype": "Tab Break",
				"label": "Connections",
				"show_dashboard": 1,
			},
		],
		custom=False,
		autoname="field:title",
		naming_rule="By fieldname",
	).insert(ignore_if_duplicate=True)


def create_test_doctype_b_with_test_child_table_with_link_to_doctype_a():
	new_doctype(
		"Test Doctype B With Child Table With Link To Doctype A",
		fields=[
			{"fieldname": "title", "fieldtype": "Data", "label": "Title", "unique": 1},
			{
				"fieldname": "child_table",
				"fieldtype": "Table",
				"label": "Child Table",
				"options": "Test Child Table With Link To Doctype A",
			},
			{
				"fieldname": "connections_tab",
				"fieldtype": "Tab Break",
				"label": "Connections",
				"show_dashboard": 1,
			},
		],
		custom=False,
		autoname="field:title",
		naming_rule="By fieldname",
	).insert(ignore_if_duplicate=True)


def create_test_doctype_c_with_duplicate_link_to_doctype_a():
	new_doctype(
		"Test Unrelated Child Table With Link To Doctype A",
		istable=1,
		fields=[
			{
				"fieldname": "test_doctype_a_with_test_child_table_with_link_to_doctype_b",
				"fieldtype": "Link",
				"label": "Test Doctype A With Child Table With Link To Doctype B",
				"options": "Test Doctype A With Child Table With Link To Doctype B",
			}
		],
		custom=False,
	).insert(ignore_if_duplicate=True)

	new_doctype(
		"Test Doctype C With Duplicate Link To Doctype A",
		fields=[
			{"fieldname": "title", "fieldtype": "Data", "label": "Title", "unique": 1},
			{
				"fieldname": "unrelated_child_table",
				"fieldtype": "Table",
				"label": "Unrelated Child Table",
				"options": "Test Unrelated Child Table With Link To Doctype A",
			},
			{
				"fieldname": "child_table",
				"fieldtype": "Table",
				"label": "Child Table",
				"options": "Test Child Table With Link To Doctype A",
			},
		],
		custom=False,
		autoname="field:title",
		naming_rule="By fieldname",
	).insert(ignore_if_duplicate=True)


def get_dashboard_for_test_doctype_a_with_test_child_table_with_link_to_doctype_b():
	dashboard = frappe._dict()

	data = {
		"fieldname": "test_doctype_a_with_test_child_table_with_link_to_doctype_b",
		"internal_and_external_links": {
			"Test Doctype B With Child Table With Link To Doctype A": [
				"child_table",
				"test_doctype_b_with_test_child_table_with_link_to_doctype_a",
			],
		},
		"transactions": [
			{"label": "Reference", "items": ["Test Doctype B With Child Table With Link To Doctype A"]},
		],
	}

	dashboard.fieldname = data["fieldname"]
	dashboard.internal_and_external_links = data["internal_and_external_links"]
	dashboard.transactions = data["transactions"]

	return dashboard


def create_linked_doctypes():
	"""
	Test Doctype D and Test Doctype E linked to "ToDo"
	"""
	new_doctype(
		"Test Doctype D",
		fields=[
			{"fieldname": "title", "fieldtype": "Data", "label": "Title", "unique": 1},
			{
				"fieldname": "doclink",
				"fieldtype": "Link",
				"label": "DocLink",
				"options": "ToDo",
			},
		],
		custom=False,
		autoname="field:title",
		naming_rule="By fieldname",
	).insert(ignore_if_duplicate=True)

	new_doctype(
		"Test Doctype E",
		fields=[
			{"fieldname": "title", "fieldtype": "Data", "label": "Title", "unique": 1},
			{
				"fieldname": "todo",
				"fieldtype": "Link",
				"label": "Linked ToDo",
				"options": "ToDo",
			},
		],
		custom=False,
		autoname="field:title",
		naming_rule="By fieldname",
	).insert(ignore_if_duplicate=True)


def get_dashboard_for_todo(data: dict):
	return data | {
		"heatmap": True,
		"heatmap_message": "This is a heatmap message",
		"fieldname": "todo",
	}
