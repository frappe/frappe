# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.flow.utils.safe_exec import get_flow_safe_globals, safe_exec
from frappe.tests import IntegrationTestCase

SENDMAIL = 'frappe.sendmail(recipients=["someone@example.com"], attachments=attachments)'


class TestFlowSafeExec(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _run(self, code):
		exec_globals, _ = safe_exec(code, script_filename="test")
		return exec_globals.get("result")

	def test_namespace_offers_only_permission_respecting_functions(self):
		g = get_flow_safe_globals()
		for name in ("sql", "set_value", "get_all", "commit", "rollback", "add_index", "escape"):
			self.assertNotIn(name, g.frappe.db)
		self.assertNotIn("get_all", g.frappe)
		self.assertNotIn("qb", g.frappe)
		self.assertNotIn("csrf_token", g.frappe.session)
		self.assertIn("get_list", g.frappe)
		for name in ("get_value", "get_single_value", "exists", "count"):
			self.assertIn(name, g.frappe.db)
		# the write builtins, but not execute itself or the server-side and bound tools
		for name in ("create", "update", "delete", "run_action", "read_records", "describe", "find_doctypes"):
			self.assertIn(name, g)
		for name in (
			"execute",
			"search_knowledge",
			"search_attachments",
			"read",
			"grep",
			"subagent",
			"suggest_replies",
			"update_memory",
		):
			self.assertNotIn(name, g)

	def test_runs_code_with_the_permission_checked_helpers(self):
		for _ in range(2):
			frappe.get_doc(
				{"doctype": "ToDo", "description": "flow sandbox count", "status": "Open"}
			).insert()
		for code, expected in (
			("result = sum([1, 2, 3])", 6),
			('result = frappe.utils.cint("5")', 5),
			(
				'result = frappe.get_list("ToDo", filters={"description": "flow sandbox count"}, '
				'fields=[{"COUNT": "*", "as": "total"}])[0]["total"]',
				2,
			),
			('result = frappe.db.count("ToDo", {"description": "flow sandbox count"})', 2),
		):
			with self.subTest(code):
				self.assertEqual(self._run(code), expected)

		result = self._run('result = create("ToDo", [{"description": "made in sandbox"}])')
		self.assertEqual(len(result["created"]), 1)
		self.assertTrue(frappe.db.exists("ToDo", result["created"][0]))

	def test_refuses_imports_dunders_and_permission_bypassing_functions(self):
		for code, error in (
			("import os", ImportError),
			("result = ().__class__", SyntaxError),
			('result = frappe.db.sql("select 1")', AttributeError),
			('frappe.db.set_value("ToDo", "x", "status", "Open")', AttributeError),
			('result = frappe.get_all("ToDo")', AttributeError),
			('result = frappe.render_template("{{ 1 }}", {})', AttributeError),
		):
			with self.subTest(code), self.assertRaises(error):
				safe_exec(code)

	def test_enforces_the_users_permissions(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "secret", "status": "Open"}).insert()
		frappe.set_user("Guest")
		with self.assertRaises(PermissionError):
			safe_exec('result = create("ToDo", [{"description": "denied"}])')
		for code in (
			f'frappe.get_doc("ToDo", "{todo.name}")',
			# get_list drops the arguments that would widen the read
			'frappe.get_list("User", fields=["name"], ignore_permissions=True)',
			'frappe.db.get_list("User", fields=["name"], ignore_permissions=True)',
			'frappe.get_list("User", fields=["name"], ignore_user_permissions=True)',
			'frappe.get_list("User", fields=["name"], user="Administrator")',
		):
			with self.subTest(code), self.assertRaises(frappe.PermissionError):
				safe_exec(f"result = {code}")

	def test_get_doc_hides_fields_above_the_users_permlevel(self):
		# desk users can read a public Note at permlevels 0 and 1; its seen_by table is permlevel 2
		note = frappe.get_doc(
			{
				"doctype": "Note",
				"title": "flow permlevel",
				"public": 1,
				"seen_by": [{"user": "Administrator"}],
			}
		).insert()
		frappe.set_user(self._desk_user())
		for code in (
			f'result = frappe.get_doc("Note", "{note.name}")',
			'result = frappe.get_last_doc("Note", filters={"title": "flow permlevel"})',
		):
			with self.subTest(code):
				result = self._run(code)
				self.assertEqual(result["public"], 1)
				self.assertEqual(result["seen_by"], [])

	def test_sendmail_attaches_only_files_and_prints_the_user_can_read(self):
		file = self._private_file()
		print_ = {"print_format_attachment": 1, "doctype": "ToDo", "name": file.attached_to_name}
		attachments = [{"file_url": file.file_url}, {**print_, "doc": {"doctype": "ToDo", "name": "other"}}]
		with patch("frappe.sendmail") as sendmail:
			safe_exec(SENDMAIL, {"attachments": attachments})
		self.assertEqual(sendmail.call_args.kwargs["attachments"], [{"fid": file.name}, print_])

		frappe.set_user("Guest")
		for attachment in ({"fid": file.name}, {"file_url": file.file_url}, print_):
			with self.subTest(attachment), patch("frappe.sendmail") as sendmail:
				with self.assertRaises(frappe.PermissionError):
					safe_exec(SENDMAIL, {"attachments": [attachment]})
				sendmail.assert_not_called()

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

	def _desk_user(self):
		"""A Flow User, which Frappe also gives Desk User."""
		email = "flow-desk-user@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Desk",
					"send_welcome_email": 0,
					"roles": [{"role": "Flow User"}],
				}
			).insert(ignore_permissions=True)
		return email
