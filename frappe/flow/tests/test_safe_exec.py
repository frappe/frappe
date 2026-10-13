# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.utils.safe_exec import get_flow_safe_globals, safe_exec

SENDMAIL = 'frappe.sendmail(recipients=["someone@example.com"], attachments=attachments)'


class TestFlowSafeExecNamespace(IntegrationTestCase):
	def test_excludes_permission_bypassing_functions(self):
		g = get_flow_safe_globals()
		for name in ("sql", "set_value", "get_all", "commit", "rollback", "add_index", "escape"):
			self.assertNotIn(name, g.frappe.db)
		self.assertNotIn("get_all", g.frappe)
		self.assertNotIn("qb", g.frappe)
		self.assertNotIn("csrf_token", g.frappe.session)

	def test_includes_permission_respecting_helpers(self):
		g = get_flow_safe_globals()
		self.assertIn("get_list", g.frappe)
		for name in ("get_value", "get_single_value", "exists", "count"):
			self.assertIn(name, g.frappe.db)

	def test_injects_write_builtins_but_not_execute(self):
		g = get_flow_safe_globals()
		for name in ("create", "update", "delete", "run_action", "read_records", "describe", "find_doctypes"):
			self.assertIn(name, g)
		self.assertNotIn("execute", g)
		self.assertNotIn("search_knowledge", g)
		self.assertNotIn("search_attachments", g)
		self.assertNotIn("read", g)
		self.assertNotIn("grep", g)
		self.assertNotIn("subagent", g)
		self.assertNotIn("update_memory", g)


class TestFlowSafeExec(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _run(self, code):
		exec_globals, _ = safe_exec(code, script_filename="test")
		return exec_globals.get("result")

	def test_computation(self):
		self.assertEqual(self._run("result = sum([1, 2, 3])"), 6)

	def test_utils_available(self):
		self.assertEqual(self._run('result = frappe.utils.cint("5")'), 5)

	def test_blocks_import(self):
		with self.assertRaises(ImportError):
			safe_exec("import os")

	def test_blocks_dunder_access(self):
		with self.assertRaises(SyntaxError):
			safe_exec("result = ().__class__")

	def test_raw_sql_unavailable(self):
		with self.assertRaises(AttributeError):
			safe_exec('result = frappe.db.sql("select 1")')

	def test_set_value_unavailable(self):
		with self.assertRaises(AttributeError):
			safe_exec('frappe.db.set_value("ToDo", "x", "status", "Open")')

	def test_get_all_unavailable(self):
		with self.assertRaises(AttributeError):
			safe_exec('result = frappe.get_all("ToDo")')

	def test_get_list_supports_aggregates(self):
		frappe.get_doc({"doctype": "ToDo", "description": "agg a", "status": "Open"}).insert()
		frappe.get_doc({"doctype": "ToDo", "description": "agg b", "status": "Open"}).insert()
		rows = self._run(
			'result = frappe.get_list("ToDo", filters={"status": "Open"}, fields=[{"COUNT": "*", "as": "total"}])'
		)
		self.assertGreaterEqual(rows[0]["total"], 2)

	def test_count_returns_number(self):
		frappe.get_doc({"doctype": "ToDo", "description": "count me", "status": "Open"}).insert()
		self.assertGreaterEqual(self._run('result = frappe.db.count("ToDo")'), 1)

	def test_create_builtin_writes(self):
		result = self._run('result = create("ToDo", [{"description": "made in sandbox"}])')
		self.assertEqual(len(result["created"]), 1)
		self.assertTrue(frappe.db.exists("ToDo", result["created"][0]))

	def test_get_doc_enforces_read_permission(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "secret", "status": "Open"}).insert()
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			safe_exec(f'result = frappe.get_doc("ToDo", "{todo.name}")')

	def test_create_enforces_create_permission(self):
		frappe.set_user("Guest")
		with self.assertRaises(PermissionError):
			safe_exec('result = create("ToDo", [{"description": "denied"}])')

	def test_get_list_ignore_permissions_is_stripped(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			safe_exec('result = frappe.get_list("User", fields=["name"], ignore_permissions=True)')

	def test_db_get_list_ignore_permissions_is_stripped(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			safe_exec('result = frappe.db.get_list("User", fields=["name"], ignore_permissions=True)')

	def test_get_list_ignore_user_permissions_is_stripped(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			safe_exec('result = frappe.get_list("User", fields=["name"], ignore_user_permissions=True)')

	def test_get_list_user_impersonation_is_stripped(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			safe_exec('result = frappe.get_list("User", fields=["name"], user="Administrator")')

	def test_render_template_is_unavailable(self):
		with self.assertRaises(AttributeError):
			safe_exec('result = frappe.render_template("{{ 1 }}", {})')

	def test_sendmail_refuses_an_unreadable_print(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "secret"}).insert()
		frappe.set_user("Guest")
		attachments = [{"print_format_attachment": 1, "doctype": "ToDo", "name": todo.name}]
		with patch("frappe.sendmail") as sendmail, self.assertRaises(frappe.PermissionError):
			safe_exec(SENDMAIL, {"attachments": attachments})
		sendmail.assert_not_called()

	def test_sendmail_refuses_an_unreadable_file(self):
		file = self._private_file()
		frappe.set_user("Guest")
		for attachment in ({"fid": file.name}, {"file_url": file.file_url}):
			with self.subTest(attachment), patch("frappe.sendmail") as sendmail:
				with self.assertRaises(frappe.PermissionError):
					safe_exec(SENDMAIL, {"attachments": [attachment]})
				sendmail.assert_not_called()

	def test_sendmail_attaches_the_checked_file_and_record(self):
		file = self._private_file()
		print_ = {"print_format_attachment": 1, "doctype": "ToDo", "name": file.attached_to_name}
		attachments = [{"file_url": file.file_url}, {**print_, "doc": {"doctype": "ToDo", "name": "other"}}]
		with patch("frappe.sendmail") as sendmail:
			safe_exec(SENDMAIL, {"attachments": attachments})
		self.assertEqual(sendmail.call_args.kwargs["attachments"], [{"fid": file.name}, print_])

	def _private_file(self):
		"""A private file on an Administrator's ToDo."""
		todo = frappe.get_doc({"doctype": "ToDo", "description": "has a file"}).insert()
		return frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "flow-sendmail-test.txt",
				"content": b"private",
				"is_private": 1,
				"attached_to_doctype": "ToDo",
				"attached_to_name": todo.name,
			}
		).insert()
