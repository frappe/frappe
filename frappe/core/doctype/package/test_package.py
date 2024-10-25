# Copyright (c) 2021, Frappe Technologies and Contributors
# See license.txt

import json
import os

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestPackage(UnitTestCase):
	"""
	Unit tests for Package.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestPackage(IntegrationTestCase):
	def test_package_release(self) -> None:
		make_test_package()
		make_test_module()
		make_test_doctype()
		make_test_server_script()
		make_test_web_page()

		# make release
		frappe.get_doc(doctype="Package Release", package="Test Package", publish=1).insert()

		self.assertTrue(os.path.exists(frappe.get_site_path("packages", "test-package")))
		self.assertTrue(
			os.path.exists(frappe.get_site_path("packages", "test-package", "test_module_for_package"))
		)
		self.assertTrue(
			os.path.exists(
				frappe.get_site_path(
					"packages",
					"test-package",
					"test_module_for_package",
					"doctype",
					"test_doctype_for_package",
				)
			)
		)
		with open(
			frappe.get_site_path(
				"packages",
				"test-package",
				"test_module_for_package",
				"doctype",
				"test_doctype_for_package",
				"test_doctype_for_package.json",
			)
		) as f:
			doctype = json.loads(f.read())
			self.assertEqual(doctype["doctype"], "DocType")
			self.assertEqual(doctype["name"], "Test DocType for Package")
			self.assertEqual(doctype["fields"][0]["fieldname"], "test_field")


def make_test_package() -> None:
	if not frappe.db.exists("Package", "Test Package"):
		frappe.get_doc(
			doctype="Package", name="Test Package", package_name="test-package", readme="# Test Package"
		).insert()


def make_test_module() -> None:
	if not frappe.db.exists("Module Def", "Test Module for Package"):
		frappe.get_doc(
			doctype="Module Def",
			module_name="Test Module for Package",
			custom=1,
			app_name="frappe",
			package="Test Package",
		).insert()


def make_test_doctype() -> None:
	if not frappe.db.exists("DocType", "Test DocType for Package"):
		frappe.get_doc(
			doctype="DocType",
			name="Test DocType for Package",
			custom=1,
			module="Test Module for Package",
			autoname="Prompt",
			fields=[dict(fieldname="test_field", fieldtype="Data", label="Test Field")],
		).insert()


def make_test_server_script() -> None:
	if not frappe.db.exists("Server Script", "Test Script for Package"):
		frappe.get_doc(
			doctype="Server Script",
			name="Test Script for Package",
			module="Test Module for Package",
			script_type="DocType Event",
			reference_doctype="Test DocType for Package",
			doctype_event="Before Save",
			script='frappe.msgprint("Test")',
		).insert()


def make_test_web_page() -> None:
	if not frappe.db.exists("Web Page", "test-web-page-for-package"):
		frappe.get_doc(
			doctype="Web Page",
			module="Test Module for Package",
			main_section="Some content",
			published=1,
			title="Test Web Page for Package",
		).insert()
