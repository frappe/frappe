# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch

import frappe
from frappe.core.doctype.rq_worker.rq_worker import RQWorker
from frappe.desk.doctype.todo.todo import ToDo
from frappe.flow import ToolContext
from frappe.flow.tools.builtins import (
	BUILTIN_TOOLS,
	create,
	delete,
	describe,
	execute,
	find_doctypes,
	read_records,
	run_action,
	run_report,
	sync_builtin_tools,
	update,
)
from frappe.tests import IntegrationTestCase

CTX = ToolContext(session_id="test", agent="Test Agent", user="Administrator")

REPORT_SCRIPT = """
if not filters.company:
	frappe.throw("Company is mandatory")
columns = [
	{"fieldname": "item", "label": "Item", "fieldtype": "Data"},
	{"fieldname": "qty", "label": "Qty", "fieldtype": "Int"},
	{"fieldname": "note", "label": "Note", "fieldtype": "Data", "hidden": 1},
]
rows = [{"item": f"Item {i}", "qty": i, "note": "x"} for i in range(1, 26)]
data = [columns, rows if filters.company == "Acme" else []]
"""

REPORT_JS = """frappe.query_reports["Flow Report Probe"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1 },
		{ fieldname: "item", label: __("Item"), fieldtype: "Data" },
	],
};"""


class TestFindDoctypes(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_searches_by_name_and_module(self):
		names = {r["name"] for r in find_doctypes(search="Role", limit=200, ctx=CTX)["doctypes"]}
		singles = {r["name"] for r in find_doctypes(search="System Settings", limit=200, ctx=CTX)["doctypes"]}
		core = find_doctypes(module="Core", limit=200, ctx=CTX)["doctypes"]

		self.assertIn("Role", names)
		self.assertNotIn("Has Role", names)  # a child table that also matches "Role"
		self.assertIn("System Settings", singles)
		self.assertTrue(core)
		self.assertTrue(all(r["module"] == "Core" for r in core))

	def test_lists_only_doctypes_the_user_can_read(self):
		user = _user("flow-find-probe@example.com")
		frappe.get_doc("User", user).add_roles("Flow User")

		frappe.set_user("Guest")
		guest = {r["name"] for r in find_doctypes(search="User", limit=200, ctx=CTX)["doctypes"]}
		# the limit counts only readable ones: a Flow User reads some Flow DocTypes, not the ones in
		# between, like Flow Agent Memory
		frappe.set_user(user)
		readable = [r["name"] for r in find_doctypes(search="Flow", limit=200, ctx=CTX)["doctypes"]]
		first = [r["name"] for r in find_doctypes(search="Flow", limit=4, ctx=CTX)["doctypes"]]

		self.assertNotIn("User", guest)
		self.assertEqual(first, readable[:4])
		self.assertEqual(len(first), 4)

	def test_administrator_gets_every_match_and_the_total(self):
		# as if no role could read anything
		nothing = frappe._dict(can_read=[], all_read=[], build_permissions=lambda: None)
		with patch("frappe.get_user", return_value=nothing):
			everything = find_doctypes(search="Flow", limit=200, ctx=CTX)["doctypes"]
			result = find_doctypes(search="Flow", limit=2, ctx=CTX)

		self.assertIn("Flow Agent", {r["name"] for r in everything})
		self.assertEqual(result, {"total": len(everything), "doctypes": everything[:2]})


class TestDescribe(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_returns_fields_and_permissions(self):
		result = describe(doctype="ToDo", ctx=CTX)

		self.assertEqual(result["doctype"], "ToDo")
		self.assertIn("description", {f["fieldname"] for f in result["fields"]})
		types = {f["type"] for f in result["fields"]}
		self.assertNotIn("Section Break", types)
		self.assertNotIn("Column Break", types)
		self.assertEqual(set(result["permissions"]), {"read", "write", "create", "delete"})

	def test_needs_read_permission_a_child_tables_through_its_parent(self):
		user = _user("flow-describe-probe@example.com")

		frappe.set_user("Guest")
		with self.assertRaises(PermissionError):
			describe(doctype="User", ctx=CTX)

		frappe.set_user(user)
		result = describe(doctype="Contact Phone", ctx=CTX)
		self.assertIn("phone", {f["fieldname"] for f in result["fields"]})
		self.assertTrue(result["permissions"]["read"])


class TestReadRecords(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_reads_matching_records_newest_first_with_their_total(self):
		# by name, the older one comes first
		older = frappe.get_doc({"doctype": "ToDo", "description": "read probe"}).insert(
			set_name="flow-read-a"
		)
		newer = frappe.get_doc({"doctype": "ToDo", "description": "read probe"}).insert(
			set_name="flow-read-b"
		)
		frappe.db.set_value("ToDo", older.name, "creation", "2020-01-01", update_modified=False)
		probe = {"description": "read probe"}

		every = read_records(doctype="ToDo", filters=probe, ctx=CTX)
		first = read_records(doctype="ToDo", filters=probe, fields=["name", "description"], limit=1, ctx=CTX)
		capped = read_records(doctype="DocType", limit=10_000, ctx=CTX)["records"]

		self.assertEqual(every, {"total": 2, "records": [{"name": newer.name}, {"name": older.name}]})
		self.assertEqual(first, {"total": 2, "records": [{"name": newer.name, "description": "read probe"}]})
		self.assertLessEqual(len(capped), 200)

	def test_a_virtual_doctype_is_counted_by_its_controller(self):
		workers = [{"name": f"worker-{i}"} for i in range(3)]
		with (
			patch.object(RQWorker, "get_list", return_value=workers),
			patch.object(RQWorker, "get_count", return_value=7),
		):
			result = read_records(doctype="RQ Worker", limit=2, ctx=CTX)

		self.assertEqual(result, {"total": 7, "records": workers[:2]})

	def test_reads_a_single_when_it_matches_the_filters(self):
		# CI's site skips the setup wizard, which sets the time zone
		frappe.db.set_single_value("System Settings", "time_zone", "Asia/Kolkata")

		[values] = read_records(doctype="System Settings", ctx=CTX)["records"]
		self.assertEqual((values["name"], values["time_zone"]), ("System Settings", "Asia/Kolkata"))
		for filters, fields, records in (
			(None, ["time_zone"], [{"time_zone": "Asia/Kolkata"}]),
			({"time_zone": "Asia/Kolkata"}, ["name"], [{"name": "System Settings"}]),
			({"time_zone": "UTC"}, None, []),
		):
			with self.subTest(filters=filters, fields=fields):
				result = read_records(doctype="System Settings", filters=filters, fields=fields, ctx=CTX)
				self.assertEqual(result, {"total": len(records), "records": records})

		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			read_records(doctype="System Settings", ctx=CTX)

	def test_reads_child_rows_and_their_total_through_readable_parents(self):
		user = _user("flow-child-probe@example.com")  # reads only the Contacts they own
		mine = {_contact_with_phone(owner=user) for _ in range(2)}
		_contact_with_phone(owner="Administrator")
		frappe.set_user(user)

		rows = read_records(doctype="Contact Phone", fields=["parent"], ctx=CTX)["records"]
		result = read_records(doctype="Contact Phone", fields=["parent"], limit=1, ctx=CTX)

		self.assertEqual({r["parent"] for r in rows}, mine)
		self.assertEqual((result["total"], len(result["records"])), (2, 1))

	def test_a_child_table_of_several_doctypes_reads_through_the_given_one(self):
		for parent_doctype in (None, "ToDo"):  # none given, or one the table isn't in
			with (
				self.subTest(parent_doctype=parent_doctype),
				self.assertRaisesRegex(ValueError, "pass parent_doctype, one of:.*Role Profile"),
			):
				read_records(doctype="Has Role", parent_doctype=parent_doctype, ctx=CTX)

		user = _user("flow-collision-probe@example.com")
		frappe.get_doc("User", user).add_roles("System Manager")
		# a Role Profile named like the user, whose role rows match the user by name
		frappe.get_doc(
			{"doctype": "Role Profile", "role_profile": user, "roles": [{"role": "System Manager"}]}
		).insert()

		rows = read_records(
			doctype="Has Role",
			filters={"parent": user},
			fields=["parenttype"],
			parent_doctype="User",
			ctx=CTX,
		)["records"]
		# execute's sandbox calls the function unchecked, where filters can be a list
		listed = read_records.func(
			doctype="Has Role",
			filters=[["parent", "=", user]],
			fields=["parenttype"],
			parent_doctype="User",
			ctx=CTX,
		)["records"]

		self.assertEqual({r["parenttype"] for r in rows}, {"User"})
		self.assertEqual({r["parenttype"] for r in listed}, {"User"})


class TestRunReport(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		cls.enterClassContext(patch("frappe.utils.safe_exec.is_safe_exec_enabled", return_value=True))
		super().setUpClass()

	def setUp(self):
		self.report = self.make_report(
			"Flow Report Probe",
			"Script Report",
			report_script=REPORT_SCRIPT,
			javascript=REPORT_JS,
			filters=[{"fieldname": "warehouse", "label": "Warehouse", "fieldtype": "Data", "mandatory": 1}],
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_returns_shown_columns_capped_rows_the_count_and_total(self):
		result = run_report(report_name=self.report.name, filters={"company": "Acme"}, limit=10, ctx=CTX)

		self.assertEqual(
			result["columns"], [{"fieldname": "item", "label": "Item"}, {"fieldname": "qty", "label": "Qty"}]
		)
		self.assertEqual(result["rows"][0], {"item": "Item 1", "qty": 1})
		self.assertEqual(len(result["rows"]), 10)
		self.assertEqual(result["row_count"], 25)
		self.assertNotIn("total_row", result)
		self.assertNotIn("available_filters", result)

		self.report.db_set("add_total_row", 1)
		result = run_report(report_name=self.report.name, filters={"company": "Acme"}, limit=10, ctx=CTX)
		rows = run_report(report_name=self.report.name, filters={"company": "Acme"}, limit=200, ctx=CTX)[
			"rows"
		]

		self.assertEqual(result["total_row"], {"item": "Total", "qty": 325})
		self.assertEqual(result["row_count"], 25)
		# a cut keeps the head, so the count and total come before the rows
		self.assertEqual(list(result), ["columns", "row_count", "total_row", "rows"])
		self.assertEqual((len(rows), rows[-1]), (25, {"item": "Item 25", "qty": 25}))

	def test_a_failed_run_gives_the_reports_own_error_and_its_filters(self):
		# frappe's failure log survives the rollback
		with patch("frappe.log_error"), self.assertRaises(ValueError) as caught:
			run_report(report_name=self.report.name, ctx=CTX)
		self.assertIn("Company is mandatory", str(caught.exception))
		self.assertIn("(* = required) warehouse*, company*, item", str(caught.exception))

		def fail(*args, **kwargs):
			try:
				raise KeyError("owner")
			except KeyError:  # frappe's failure log can't write in the report's read-only transaction
				raise frappe.InReadOnlyMode("Site is running in read only mode")

		with patch("frappe.desk.query_report.run", side_effect=fail), self.assertRaises(ValueError) as caught:
			run_report(report_name=self.report.name, filters={"company": "Acme"}, ctx=CTX)
		self.assertTrue(str(caught.exception).startswith("'owner'\n"))

	def test_an_empty_run_lists_the_filters(self):
		filters = "(* = required) warehouse*, company*, item"
		result = run_report(report_name=self.report.name, filters={"company": "Other"}, ctx=CTX)
		self.assertEqual((result["row_count"], result["available_filters"]), (0, filters))

		self.report.db_set("report_script", "pass")  # a report that returns nothing at all
		result = run_report(report_name=self.report.name, filters={"company": "Acme"}, ctx=CTX)
		self.assertEqual((result["rows"], result["available_filters"]), ([], filters))

	def test_refuses_a_report_it_cannot_run(self):
		builder = self.make_report("Flow Builder Probe", "Report Builder")
		# never run it here: a query report opens its own transaction
		query = self.make_report(
			"Flow Query Probe", "Query Report", query="select name from tabToDo where owner = %(owner)s"
		)
		for report, error in ((builder.name, "read_records"), (query.name, "^Missing filters: owner$")):
			with self.subTest(report), self.assertRaisesRegex(ValueError, error):
				run_report(report_name=report, ctx=CTX)

		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			run_report(report_name=self.report.name, filters={"company": "Acme"}, ctx=CTX)

	def test_query_report_runs_with_given_or_saved_filters(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "query report probe"}).insert()
		query = self.make_report(
			"Flow Query Probe",
			"Query Report",
			query='select name as "ToDo:Link/ToDo:120", description as "Description:Data:200" '
			"from tabToDo where description = %(description)s",
		)
		custom = self.make_report(
			"Flow Custom Probe",
			"Custom Report",
			reference_report=query.name,
			json=json.dumps({"filters": {"description": "query report probe"}}),
		)

		# a query report opens its own transaction; keep it in the test's
		with patch.object(frappe.db, "begin"), patch.object(frappe.db, "rollback"):
			result = run_report(
				report_name=query.name, filters={"description": "query report probe"}, ctx=CTX
			)
		with patch("frappe.desk.query_report.run", return_value={"columns": [], "result": []}) as ran:
			run_report(report_name=custom.name, ctx=CTX)

		self.assertEqual(
			result["columns"],
			[{"fieldname": "todo", "label": "ToDo"}, {"fieldname": "description", "label": "Description"}],
		)
		self.assertEqual(result["rows"], [{"todo": todo.name, "description": "query report probe"}])
		ran.assert_called_once()

	def test_only_a_prepared_report_runs_in_the_background(self):
		args = {"report_name": self.report.name}
		self.assertFalse(run_report.background(args))
		self.report.db_set("prepared_report", 1)
		self.assertTrue(run_report.background(args))
		self.assertFalse(run_report.background({}))

	def make_report(self, name: str, report_type: str, **values):
		return frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": name,
				"ref_doctype": "ToDo",
				"report_type": report_type,
				"is_standard": "No",
				**values,
			}
		).insert()


class TestExecute(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		cls.enterClassContext(patch("frappe.utils.safe_exec.is_safe_exec_enabled", return_value=True))
		super().setUpClass()

	def tearDown(self):
		frappe.db.rollback()

	def test_returns_the_result_variable(self):
		for code, expected in (("result = 1 + 1", 2), ("x = 5", None)):
			with self.subTest(code):
				self.assertEqual(execute(code=code, description="Compute a value", ctx=CTX), expected)

	def test_a_caught_write_failure_still_fails_the_call(self):
		code = """
try:
	create("ToDo", [{"description": "ai execute works"}, {"description": "ai execute fails"}])
except Exception:
	pass
result = "done"
"""
		with (
			_todo_hook_fails("after_insert", "ai execute fails"),
			self.assertRaisesRegex(ValueError, "Record 2 of 2: hook failed"),
		):
			execute(code=code, description="Create two ToDos", ctx=CTX)


class TestWriteTools(IntegrationTestCase):
	def setUp(self):
		self.todo = frappe.get_doc({"doctype": "ToDo", "description": "ai write probe"}).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_create_update_and_delete_every_record(self):
		result = create(doctype="ToDo", records=[{"description": "ai create probe"}], ctx=CTX)
		self.assertEqual(result["doctype"], "ToDo")
		[name] = result["created"]
		self.assertEqual(frappe.db.get_value("ToDo", name, "description"), "ai create probe")

		names = [self.todo.name, name]
		result = update(doctype="ToDo", names=names, values={"status": "Closed"}, ctx=CTX)
		self.assertEqual(result["updated"], names)
		self.assertEqual(
			frappe.get_all("ToDo", {"name": ["in", names]}, pluck="status"), ["Closed", "Closed"]
		)

		self.assertEqual(delete(doctype="ToDo", names=names, ctx=CTX)["deleted"], names)
		self.assertFalse(frappe.db.exists("ToDo", {"name": ["in", names]}))

	def test_one_failed_record_changes_none(self):
		failing = frappe.get_doc({"doctype": "ToDo", "description": "ai write fails"}).insert()
		names = [self.todo.name, failing.name]
		todos = {"description": ["in", ["ai write probe", "ai write fails", "ai create works"]]}
		before = frappe.get_all("ToDo", todos, ["name", "status", "docstatus"], order_by="name")
		new = [{"description": "ai create works"}, {"description": "ai write fails"}]
		for tool, hook, args, record in (
			(create, "after_insert", {"records": new}, "Record 2 of 2"),
			(update, "on_update", {"names": names, "values": {"status": "Closed"}}, failing.name),
			(delete, "after_delete", {"names": names}, failing.name),
			(run_action, "on_discard", {"names": names, "action": "discard"}, failing.name),
		):
			with self.subTest(tool.name), _todo_hook_fails(hook, "ai write fails"):
				with self.assertRaisesRegex(ValueError, f"{record}: hook failed\nNothing was saved."):
					tool(doctype="ToDo", **args, ctx=CTX)
				self.assertEqual(
					frappe.get_all("ToDo", todos, ["name", "status", "docstatus"], order_by="name"), before
				)

	def test_refuses_missing_and_forbidden_records(self):
		probe = _user("flow-action-probe@example.com")
		closed = {"values": {"status": "Closed"}}
		comment = {"action": "add_comment", "args": {"comment_type": "Comment", "text": "unseen"}}
		for user, tool, args, error in (
			("Administrator", update, {"names": ["does-not-exist"], **closed}, "does-not-exist"),
			("Administrator", delete, {"names": ["does-not-exist"]}, "does-not-exist"),
			("Guest", update, {"names": [self.todo.name], **closed}, "No permission"),
			("Guest", delete, {"names": [self.todo.name]}, "No permission"),
			# every user reads ToDo, but only the ones they own or are assigned
			(probe, run_action, {"names": [self.todo.name], **comment}, f"{self.todo.name}: PermissionError"),
		):
			with self.subTest(tool.name, user=user):
				frappe.set_user(user)
				with self.assertRaisesRegex(ValueError, error):
					tool(doctype="ToDo", **args, ctx=CTX)
		self.assertFalse(frappe.db.exists("Comment", {"reference_name": self.todo.name}))

		frappe.set_user("Guest")
		with self.assertRaises(PermissionError):
			create(doctype="User", records=[{"email": "x@example.com"}], ctx=CTX)

	def test_a_lost_savepoint_is_reported(self):
		def end_savepoint_then_fail(doc, *args, **kwargs):
			frappe.db.release_savepoint("flow_batch")
			raise frappe.ValidationError("after the savepoint")

		with (
			patch.object(ToDo, "on_update", end_savepoint_then_fail),
			self.assertRaisesRegex(
				ValueError, "after the savepoint\nSome earlier changes may already be committed"
			),
		):
			update(doctype="ToDo", names=[self.todo.name], values={"status": "Closed"}, ctx=CTX)


class TestSyncBuiltinTools(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_syncs_one_row_per_builtin_that_resolves_to_the_code(self):
		sync_builtin_tools()
		sync_builtin_tools()  # a second run updates the rows in place

		names = [builtin.name for builtin in BUILTIN_TOOLS]
		self.assertEqual(
			sorted(frappe.get_all("Flow Tool", {"name": ["in", names]}, pluck="name")), sorted(names)
		)
		runtime = frappe.get_doc("Flow Tool", "describe").to_tool()
		self.assertEqual(runtime.name, "describe")
		self.assertIn("doctype", runtime.parameters["properties"])
		# writes wait for the user's approval
		confirmed = frappe.get_all(
			"Flow Tool", {"name": ["in", names], "requires_confirmation": 1}, pluck="name"
		)
		self.assertLessEqual({"create", "update", "delete"}, set(confirmed))
		# a per-call background rule stays in code
		report = frappe.get_doc("Flow Tool", "run_report")
		self.assertEqual(report.background, 0)
		self.assertTrue(callable(report.to_tool().background))


def _user(email: str) -> str:
	"""A user with no roles, so permission checks apply."""
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": "Probe", "send_welcome_email": 0}
		).insert(ignore_permissions=True)
	return email


def _todo_hook_fails(hook: str, description: str):
	"""ToDo's `hook` raises for the ToDo with this description, after that record's write."""

	def fail(doc, *args, **kwargs):
		if doc.description == description:
			raise frappe.ValidationError("hook failed")

	return patch.object(ToDo, hook, fail, create=True)


def _contact_with_phone(owner: str) -> str:
	contact = frappe.get_doc(
		{"doctype": "Contact", "first_name": "Flow Probe", "phone_nos": [{"phone": "+1 555 0100"}]}
	).insert()
	frappe.db.set_value("Contact", contact.name, "owner", owner)
	return contact.name
