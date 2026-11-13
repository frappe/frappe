# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.flow.utils.safe_exec import get_flow_safe_globals, safe_exec
from frappe.tests import IntegrationTestCase
from frappe.utils.safe_exec import ServerScriptNotEnabled

SENDMAIL = 'frappe.sendmail(recipients=["someone@example.com"], attachments=attachments)'


class TestFlowSafeExec(IntegrationTestCase):
	def setUp(self):
		self.enterContext(patch("frappe.utils.safe_exec.is_safe_exec_enabled", return_value=True))

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _run(self, code):
		exec_globals, _ = safe_exec(code, script_filename="test")
		return exec_globals.get("result")

	def test_runs_nothing_while_server_scripts_are_off(self):
		with (
			patch("frappe.utils.safe_exec.is_safe_exec_enabled", return_value=False),
			self.assertRaises(ServerScriptNotEnabled),
		):
			self._run("result = 1")

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
			"read_attachment",
			"read",
			"grep",
			"subagent",
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

	def test_get_value_reads_a_single(self):
		time_zone = frappe.db.get_single_value("System Settings", "time_zone")
		for code, expected in (
			('frappe.db.get_value("System Settings", None, "time_zone")', time_zone),
			('frappe.db.get_value("System Settings", "System Settings", ["time_zone"])', [time_zone]),
			(
				'frappe.db.get_value("System Settings", None, "time_zone", as_dict=True)',
				{"time_zone": time_zone},
			),
		):
			with self.subTest(code):
				self.assertEqual(self._run(f"result = {code}"), expected)
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			self._run('result = frappe.db.get_value("System Settings", None, "time_zone")')

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

	def test_enqueue_takes_only_the_function_and_its_arguments(self):
		with patch("frappe.flow.utils.safe_exec.safe_enqueue") as queued:
			self._run('frappe.enqueue("frappe.ping", note="x")')
			queued.assert_called_once_with("frappe.ping", note="x")
			for option in (
				'queue="long"',
				"timeout=86400",
				"at_front=True",
				'job_id="x"',
				'on_success="os.getcwd"',
			):
				with (
					self.subTest(option),
					self.assertRaisesRegex(frappe.ValidationError, "only the function"),
				):
					self._run(f'frappe.enqueue("frappe.ping", {option})')
			queued.assert_called_once()

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

	def test_a_lookup_by_filters_does_not_tell_that_a_hidden_record_matches(self):
		frappe.get_doc({"doctype": "ToDo", "description": "flow hidden match"}).insert()
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "flow-sandbox-lookup@example.com",
				"first_name": "Lookup",
				"send_welcome_email": 0,
				"roles": [{"role": "Flow User"}],
			}
		).insert(ignore_permissions=True)
		frappe.set_user(user.name)
		own = frappe.get_doc({"doctype": "ToDo", "description": "flow own match"}).insert()
		for call in ("get_doc", "get_last_doc"):
			with self.subTest(call):
				found = self._run(f'result = frappe.{call}("ToDo", {{"description": "flow own match"}})')
				self.assertEqual(found["name"], own.name)
				# hidden or missing: both are not found
				for description in ("flow hidden match", "flow no match"):
					with self.assertRaises(frappe.DoesNotExistError):
						self._run(f'frappe.{call}("ToDo", {{"description": "{description}"}})')
		with self.subTest("filters as a tuple"):
			found = self._run('result = frappe.get_doc("ToDo", ("description", "=", "flow own match"))')
			self.assertEqual(found["name"], own.name)
			for description in ("flow hidden match", "flow no match"):
				with self.assertRaises(frappe.DoesNotExistError):
					self._run(f'frappe.get_doc("ToDo", ("description", "=", "{description}"))')

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
		self.assertEqual(
			sendmail.call_args.kwargs["attachments"],
			[{"fid": file.name}, {**print_, "print_format": "Standard"}],
		)

		frappe.set_user("Guest")
		for attachment in ({"fid": file.name}, {"file_url": file.file_url}, print_):
			with self.subTest(attachment), patch("frappe.sendmail") as sendmail:
				with self.assertRaises(frappe.PermissionError):
					safe_exec(SENDMAIL, {"attachments": [attachment]})
				sendmail.assert_not_called()

	def test_sendmail_takes_no_sender(self):
		# frappe.sendmail's own argument order still works
		for call in (
			'frappe.sendmail(["a@example.com"], subject="Hi", message="Body", sender="")',
			'frappe.sendmail(["a@example.com"], "", "Hi", "Body")',
		):
			with self.subTest(call), patch("frappe.sendmail") as sendmail:
				self._run(call)
				sendmail.assert_called_once_with(
					recipients=["a@example.com"], subject="Hi", message="Body", attachments=[]
				)
		for call in (
			'frappe.sendmail(recipients=["a@example.com"], sender="ceo@example.com")',
			'frappe.sendmail(["a@example.com"], "ceo@example.com", "Hi")',
		):
			with self.subTest(call), patch("frappe.sendmail") as sendmail:
				with self.assertRaisesRegex(frappe.ValidationError, "takes no sender"):
					self._run(call)
				sendmail.assert_not_called()

	def test_sendmail_refers_only_to_records_the_user_may_email(self):
		user = self._desk_user()
		mine = frappe.get_doc({"doctype": "ToDo", "description": "mine", "allocated_to": user}).insert()
		other = frappe.get_doc({"doctype": "ToDo", "description": "not mine"}).insert()
		note = frappe.get_doc(
			{"doctype": "Communication", "subject": "Private", "communication_type": "Communication"}
		).insert()
		frappe.set_user(user)
		with patch("frappe.sendmail") as sendmail:
			self._run(
				f'frappe.sendmail(["a@example.com"], reference_doctype="ToDo", reference_name="{mine.name}")'
			)
			sendmail.assert_called_once()
		for call in (
			f'frappe.sendmail(["a@example.com"], reference_doctype="ToDo", reference_name="{other.name}")',
			f'frappe.sendmail(["a@example.com"], doctype="ToDo", name="{other.name}")',
			f'frappe.sendmail(["a@example.com"], "", "Hi", "Body", False, True, "ToDo", "{other.name}")',
			'frappe.sendmail(["a@example.com"], reference_doctype="Flow Tool")',
			f'frappe.sendmail(["a@example.com"], communication="{note.name}")',
		):
			with self.subTest(call), patch("frappe.sendmail") as sendmail:
				with self.assertRaises(frappe.PermissionError):
					self._run(call)
				sendmail.assert_not_called()

	def test_sendmail_prints_with_a_format_the_user_may_print_with(self):
		user = self._desk_user()
		todo = frappe.get_doc(
			{"doctype": "ToDo", "description": "Renew the lease", "allocated_to": user}
		).insert()
		default = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": "_Test Flow Manager ToDo",
				"doc_type": "ToDo",
				"custom_format": 1,
				"print_format_type": "Jinja",
				"html": "{{ doc.name }}",
				"roles": [{"role": "System Manager"}],
			}
		).insert()
		attachments = [{"print_format_attachment": 1, "doctype": "ToDo", "name": todo.name}]
		frappe.set_user(user)
		with (
			patch.object(frappe.get_meta("ToDo"), "default_print_format", default.name),
			patch("frappe.sendmail") as sendmail,
		):
			safe_exec(SENDMAIL, {"attachments": attachments})
		self.assertEqual(sendmail.call_args.kwargs["attachments"][0]["print_format"], "Standard")

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
