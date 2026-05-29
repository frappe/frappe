# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.ai.tools.builtins import (
	BUILTIN_TOOLS,
	create,
	delete,
	describe,
	execute,
	find_doctypes,
	read,
	sync_builtin_tools,
	update,
)
from frappe.tests import IntegrationTestCase


class TestFindDoctypes(IntegrationTestCase):
	def test_search_matches_by_keyword(self):
		names = {r["name"] for r in find_doctypes(search="ToDo")}
		self.assertIn("ToDo", names)

	def test_filters_by_module(self):
		rows = find_doctypes(module="Core", limit=200)
		self.assertTrue(rows)
		self.assertTrue(all(r["module"] == "Core" for r in rows))

	def test_excludes_child_tables(self):
		names = {r["name"] for r in find_doctypes(search="Role", limit=200)}
		self.assertIn("Role", names)
		self.assertNotIn("Has Role", names)  # a child table that also matches "Role"

	def test_includes_single_doctypes(self):
		names = {r["name"] for r in find_doctypes(search="System Settings", limit=200)}
		self.assertIn("System Settings", names)  # a single DocType

	def test_respects_read_permission(self):
		frappe.set_user("Guest")
		try:
			names = {r["name"] for r in find_doctypes(search="User", limit=200)}
			self.assertNotIn("User", names)
		finally:
			frappe.set_user("Administrator")


class TestDescribe(IntegrationTestCase):
	def test_returns_fields_and_permissions(self):
		result = describe(doctype="ToDo")

		self.assertEqual(result["doctype"], "ToDo")
		fieldnames = {f["fieldname"] for f in result["fields"]}
		self.assertIn("description", fieldnames)
		self.assertEqual(set(result["permissions"]), {"read", "write", "create", "delete"})

	def test_excludes_layout_fields(self):
		result = describe(doctype="ToDo")
		types = {f["type"] for f in result["fields"]}
		self.assertNotIn("Section Break", types)
		self.assertNotIn("Column Break", types)

	def test_permission_denied_raises(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				describe(doctype="User")
		finally:
			frappe.set_user("Administrator")


class TestRead(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_reads_matching_records(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "ai builtin read probe"}).insert()

		rows = read(doctype="ToDo", filters={"description": "ai builtin read probe"})

		self.assertEqual([r["name"] for r in rows], [todo.name])

	def test_limit_is_capped(self):
		rows = read(doctype="DocType", limit=10_000)
		self.assertLessEqual(len(rows), 200)

	def test_returns_requested_fields(self):
		frappe.get_doc({"doctype": "ToDo", "description": "fields probe"}).insert()
		rows = read(doctype="ToDo", filters={"description": "fields probe"}, fields=["name", "description"])
		self.assertEqual(rows[0]["description"], "fields probe")


class TestExecute(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		cls.enterClassContext(cls.enable_safe_exec())
		super().setUpClass()

	def tearDown(self):
		frappe.db.rollback()

	def test_returns_result_variable(self):
		self.assertEqual(execute(code="result = 1 + 1"), 2)

	def test_no_result_returns_none(self):
		self.assertIsNone(execute(code="x = 5"))

	def test_can_read_via_frappe(self):
		count = execute(code="result = frappe.db.count('DocType')")
		self.assertIsInstance(count, int)

	def test_imports_are_blocked(self):
		with self.assertRaises(Exception):
			execute(code="import os\nresult = os.getcwd()")


class TestCreate(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_requires_confirmation(self):
		self.assertTrue(create.requires_confirmation)

	def test_creates_doc_with_values(self):
		result = create(doctype="ToDo", values={"description": "ai create probe"})

		self.assertEqual(result["doctype"], "ToDo")
		self.assertTrue(frappe.db.exists("ToDo", result["name"]))
		self.assertEqual(frappe.db.get_value("ToDo", result["name"], "description"), "ai create probe")

	def test_permission_denied_raises(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			create(doctype="User", values={"email": "x@example.com"})

	def test_missing_required_field_raises(self):
		# ToDo.description is mandatory; the doctype's own validation should fire.
		with self.assertRaises(frappe.MandatoryError):
			create(doctype="ToDo", values={})


class TestUpdate(IntegrationTestCase):
	def setUp(self):
		self.todo = frappe.get_doc({"doctype": "ToDo", "description": "ai update probe"}).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_requires_confirmation(self):
		self.assertTrue(update.requires_confirmation)

	def test_modifies_doc_fields(self):
		update(doctype="ToDo", name=self.todo.name, values={"status": "Closed"})

		self.assertEqual(frappe.db.get_value("ToDo", self.todo.name, "status"), "Closed")

	def test_runs_doctype_validation(self):
		# Status is a Select field with a fixed set; an invalid value should error.
		with self.assertRaises(frappe.ValidationError):
			update(doctype="ToDo", name=self.todo.name, values={"status": "Not A Real Status"})

	def test_missing_record_raises(self):
		with self.assertRaises(frappe.DoesNotExistError):
			update(doctype="ToDo", name="does-not-exist", values={"status": "Closed"})

	def test_permission_denied_raises(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			update(doctype="ToDo", name=self.todo.name, values={"status": "Closed"})


class TestDelete(IntegrationTestCase):
	def setUp(self):
		self.todo = frappe.get_doc({"doctype": "ToDo", "description": "ai delete probe"}).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_requires_confirmation(self):
		self.assertTrue(delete.requires_confirmation)

	def test_removes_doc(self):
		result = delete(doctype="ToDo", name=self.todo.name)

		self.assertTrue(result["deleted"])
		self.assertFalse(frappe.db.exists("ToDo", self.todo.name))

	def test_missing_record_raises(self):
		with self.assertRaises(frappe.DoesNotExistError):
			delete(doctype="ToDo", name="does-not-exist")

	def test_permission_denied_raises(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			delete(doctype="ToDo", name=self.todo.name)


class TestSyncBuiltinTools(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_creates_rows_for_all_builtins(self):
		sync_builtin_tools()
		for builtin in BUILTIN_TOOLS:
			self.assertTrue(frappe.db.exists("AI Tool", builtin.name))

	def test_resolves_back_to_runtime_tool(self):
		sync_builtin_tools()
		doc = frappe.get_doc("AI Tool", "describe")
		runtime = doc.to_tool()
		self.assertEqual(runtime.name, "describe")
		self.assertIn("doctype", runtime.parameters["properties"])

	def test_is_idempotent(self):
		sync_builtin_tools()
		sync_builtin_tools()
		count = frappe.db.count("AI Tool", {"slug": "read"})
		self.assertEqual(count, 1)
