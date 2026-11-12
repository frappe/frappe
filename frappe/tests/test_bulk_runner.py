# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.api import bulk, bulk_actions
from frappe.api.bulk import QUEUED, BulkAction, run_bulk
from frappe.api.utils import FrappeValueError
from frappe.tests import IntegrationTestCase
from frappe.tests.utils import whitelist_for_tests
from frappe.utils.task_queue import _execute_task

PREFIX = "bulk47062"
USER = "bulk47062@example.com"


class Crash(BaseException):
	"""Not an Exception: it ends the run the way a killed worker does, past the per-record catch."""


def touch_one(doctype, name, fail=(), queue=(), crash=None, values=None):
	"""Test action: set a marker on the ToDo, fail or queue the named ones."""
	if name in fail:
		frappe.throw(f"<b>{name}</b> refused")
	if name == crash:
		raise Crash
	frappe.db.set_value(doctype, name, "description", f"{PREFIX} touched")
	return QUEUED if name in queue else None


@whitelist_for_tests(methods=["POST"])
def stamp_one(doctype: str, name: str, text: str = "stamped"):
	"""Test bulk_call method: a whitelisted record function that checks the record's right itself."""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")
	frappe.db.set_value(doctype, name, "description", f"{PREFIX} {text}")
	frappe.msgprint(frappe._("stamped"))


@whitelist_for_tests(methods=["GET"])
def read_only_one(doctype: str, name: str):
	frappe.db.set_value(doctype, name, "description", f"{PREFIX} read only")


def unlisted_one(doctype: str, name: str):
	frappe.db.set_value(doctype, name, "description", f"{PREFIX} unlisted")


def add_count(params, result):
	return {"count": len(result["done"])}


TOUCH = BulkAction("Touch", touch_one)
COUNT = BulkAction("Count", touch_one, finish=add_count)
BACKGROUND = BulkAction("Touch", touch_one, background=True)


class TestBulkRunner(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(self.cleanup)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.form_dict.clear()
		self.names = [self.make_todo(i) for i in range(4)]

	def cleanup(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for name in frappe.get_all("ToDo", {"description": ["like", f"{PREFIX}%"]}, pluck="name"):
			frappe.delete_doc("ToDo", name, force=True)
		frappe.db.delete("Background Task", {"task_name": ["like", "Touch%"]})
		frappe.db.delete("Background Task", {"task_name": ["like", "Count%"]})
		frappe.db.delete("Background Task", {"task_name": ["like", "Stamp One%"]})
		frappe.db.commit()  # nosemgrep

	def make_todo(self, index: int, **values) -> str:
		doc = frappe.get_doc({"doctype": "ToDo", "description": f"{PREFIX} {index}", **values}).insert()
		return doc.name

	def run_touch(self, names=None, **params):
		frappe.form_dict.names = self.names if names is None else names
		return run_bulk(TOUCH, "ToDo", params=params)

	def make_user(self):
		if not frappe.db.exists("User", USER):
			frappe.get_doc(
				{"doctype": "User", "email": USER, "first_name": "Bulk", "send_welcome_email": 0}
			).insert()
		return USER

	def set_gate(self, user: str, value: int):
		frappe.db.set_value("User", user, "bulk_actions", value)
		frappe.clear_document_cache("User", user)

	# Gate and cap

	def test_gate_off_refuses_the_run(self):
		user = self.make_user()
		self.set_gate(user, 0)
		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			self.run_touch()
		self.assertFalse(bulk.has_gate())
		self.assertEqual(self.touched(), [])

	def test_gate_on_runs(self):
		self.assertTrue(bulk.has_gate())
		self.assertEqual(self.run_touch()["total"], 4)

	def test_cap_refuses_names_before_anything_runs(self):
		with patch.dict(frappe.conf, {"bulk_operation_limit": 3}):
			with self.assertRaises(frappe.ValidationError):
				self.run_touch()
		self.assertEqual(self.touched(), [])

	def test_cap_refuses_a_filter_that_matches_more(self):
		frappe.form_dict.filters = {"description": ["like", f"{PREFIX}%"]}
		with patch.dict(frappe.conf, {"bulk_operation_limit": 3}):
			with self.assertRaises(frappe.ValidationError):
				run_bulk(TOUCH, "ToDo")
		self.assertEqual(self.touched(), [])

	def test_cap_defaults_to_500(self):
		self.assertEqual(bulk.get_limit(), 500)

	# Selection

	def test_filter_selects_what_the_list_shows(self):
		frappe.form_dict.filters = {"description": ["like", f"{PREFIX}%"]}
		result = run_bulk(TOUCH, "ToDo")
		self.assertCountEqual(result["done"], self.names)

	def test_filter_respects_permissions(self):
		user = self.make_user()
		self.set_gate(user, 1)
		frappe.set_user(user)
		mine = self.make_todo(9)
		frappe.form_dict.filters = {"description": ["like", f"{PREFIX}%"]}

		result = run_bulk(TOUCH, "ToDo")

		self.assertEqual(result["done"], [mine])
		frappe.set_user("Administrator")
		self.assertEqual(self.touched(), [mine])

	def test_body_without_a_selection_is_refused(self):
		with self.assertRaises(ValueError):
			run_bulk(TOUCH, "ToDo")

	def test_malformed_names_fail_without_stopping_the_run(self):
		result = self.run_touch([self.names[0], {"x": 1}])
		self.assertEqual(result["total"], 2)
		self.assertEqual(result["done"], [self.names[0]])
		self.assertEqual(result["failed"][0]["name"], {"x": 1})

	# Inline and background

	def test_inline_result_shape_and_partial_failure(self):
		frappe.local.message_log = []
		result = self.run_touch(fail=[self.names[1]])
		self.assertEqual(result["total"], 4)
		self.assertCountEqual(result["done"], [self.names[0], *self.names[2:]])
		self.assertEqual(result["failed"], [{"name": self.names[1], "error": f"{self.names[1]} refused"}])
		self.assertNotIn("queued", result)
		self.assertFalse(frappe.local.message_log)

	def test_inline_run_commits_nothing(self):
		with patch("frappe.db.commit") as commit:
			self.run_touch()
		commit.assert_not_called()

	def test_failed_record_rolls_back_to_its_savepoint(self):
		self.run_touch(fail=[self.names[1]])
		self.assertCountEqual(self.touched(), [self.names[0], *self.names[2:]])

	def test_queued_outcome_is_reported_apart_from_done(self):
		result = self.run_touch(queue=[self.names[0]])
		self.assertEqual(result["queued"], [self.names[0]])
		self.assertNotIn(self.names[0], result["done"])

	def test_cross_doctype_names_carry_the_doctype(self):
		selection = bulk_actions.selection_from_docs(
			[{"doctype": "ToDo", "name": self.names[0]}, {"doctype": "ToDo", "name": "nope"}, "x"],
			with_values=False,
		)
		result = run_bulk(TOUCH, selection=selection, params={"fail": ["nope"]})
		self.assertEqual(result["done"], [{"doctype": "ToDo", "name": self.names[0]}])
		self.assertIn("ToDo", [failure["doctype"] for failure in result["failed"]])
		self.assertEqual(len(result["failed"]), 2)

	def test_above_the_threshold_it_queues_a_background_task(self):
		task_id, kwargs = self.enqueue_run()

		self.assertEqual(frappe.db.get_value("Background Task", task_id, "status"), "Queued")
		self.assertFalse(frappe.db.get_value("Background Task", task_id, "allow_user_retry"))
		self.assertEqual(self.touched(), [])

		_execute_task(**kwargs)

		task = frappe.db.get_value("Background Task", task_id, ["status", "result"], as_dict=True)
		self.assertEqual(task.status, "Completed")
		result = frappe.parse_json(task.result)
		self.assertEqual(result["total"], 4)
		self.assertCountEqual(result["done"], self.names)

	def test_background_run_with_failures_still_completes(self):
		task_id, kwargs = self.enqueue_run(fail=[self.names[2]])
		_execute_task(**kwargs)

		task = frappe.db.get_value("Background Task", task_id, ["status", "result"], as_dict=True)
		self.assertEqual(task.status, "Completed")
		self.assertEqual(frappe.parse_json(task.result)["failed"][0]["name"], self.names[2])

	def test_background_run_commits_after_each_record(self):
		_, kwargs = self.enqueue_run(crash=self.names[2])

		with self.assertRaises(Crash):
			_execute_task(**kwargs)

		frappe.db.rollback()  # what a dying worker's connection does
		self.assertCountEqual(self.touched(), self.names[:2])

	def test_background_run_reports_progress(self):
		_task_id, kwargs = self.enqueue_run()
		with patch("frappe.core.doctype.background_task.background_task.BackgroundTask._publish") as publish:
			_execute_task(**kwargs)

		progress = [call.args[0]["progress"] for call in publish.call_args_list if "stage" in call.args[0]]
		self.assertEqual(progress[-1], 100)

	def enqueue_run(self, **params):
		"""Start a run over the threshold and return its task id and what the worker would be given."""
		frappe.form_dict.names = self.names
		with patch.dict(frappe.conf, {"bulk_operation_async_threshold": 2}):
			with patch("frappe.utils.task_queue.frappe.enqueue") as enqueue:
				response = run_bulk(TOUCH, "ToDo", params=params)
				frappe.db.commit()  # nosemgrep

		self.assertEqual(frappe.response.http_status_code, 202)
		self.assertEqual(response["task_id"], response["job_id"])
		return response["task_id"], self.worker_kwargs(enqueue)

	def worker_kwargs(self, enqueue):
		"""What `enqueue_task` hands the worker, without the queueing options."""
		options = (
			"queue",
			"timeout",
			"deduplicate",
			"job_id",
			"at_front",
			"now",
			"at_front_when_starved",
			"rq_retry",
		)
		return {key: value for key, value in enqueue.call_args.kwargs.items() if key not in options}

	# Limit, finish and background

	def test_limit_replaces_the_site_cap(self):
		frappe.form_dict.names = self.names
		with self.assertRaises(frappe.ValidationError):
			run_bulk(TOUCH, "ToDo", limit=3)
		self.assertEqual(self.touched(), [])

	def test_limit_bounds_a_filter_selection(self):
		frappe.form_dict.filters = {"description": ["like", f"{PREFIX}%"]}
		with self.assertRaises(frappe.ValidationError):
			run_bulk(TOUCH, "ToDo", limit=3)

	def test_finish_adds_keys_to_an_inline_result(self):
		frappe.form_dict.names = self.names
		self.assertEqual(run_bulk(COUNT, "ToDo")["count"], 4)

	def test_finish_adds_keys_to_a_background_result(self):
		frappe.form_dict.names = self.names
		with patch.dict(frappe.conf, {"bulk_operation_async_threshold": 2}):
			with patch("frappe.utils.task_queue.frappe.enqueue") as enqueue:
				response = run_bulk(COUNT, "ToDo")
				frappe.db.commit()  # nosemgrep

		_execute_task(**self.worker_kwargs(enqueue))
		result = frappe.db.get_value("Background Task", response["task_id"], "result")
		self.assertEqual(frappe.parse_json(result)["count"], 4)

	def test_background_action_queues_below_the_threshold(self):
		frappe.form_dict.names = self.names[:1]
		with patch("frappe.utils.task_queue.frappe.enqueue"):
			response = run_bulk(BACKGROUND, "ToDo")

		self.assertEqual(frappe.response.http_status_code, 202)
		self.assertIn("task_id", response)

	# Doctype preconditions

	def test_workflow_doctype_is_refused_without_allow_edit(self):
		with patch("frappe.api.bulk_actions.get_workflow_name", return_value="Flow"):
			with self.assertRaises(frappe.ValidationError):
				bulk_actions.refuse_workflow_without_allow_edit("ToDo", {})

			frappe.form_dict.names = self.names
			with self.assertRaises(frappe.ValidationError):
				bulk_actions.bulk_delete_docs("ToDo")

		self.assertTrue(all(frappe.db.exists("ToDo", name) for name in self.names))

	def test_workflow_doctype_runs_with_allow_edit(self):
		with patch("frappe.api.bulk_actions.get_workflow_name", return_value="Flow"):
			with patch("frappe.db.get_value", return_value=1):
				bulk_actions.refuse_workflow_without_allow_edit("ToDo", {})

	# The routes

	def test_delete_route_removes_the_records(self):
		frappe.form_dict.names = self.names
		result = bulk_actions.bulk_delete_docs("ToDo")
		self.assertCountEqual(result["done"], self.names)
		self.assertFalse(any(frappe.db.exists("ToDo", name) for name in self.names))

	def test_update_route_sets_one_set_of_values_on_every_record(self):
		frappe.form_dict.update(names=self.names, values={"priority": "High"})
		result = bulk_actions.bulk_update_docs("ToDo")
		self.assertEqual(len(result["done"]), 4)
		self.assertEqual(frappe.get_all("ToDo", {"name": ["in", self.names]}, pluck="priority"), ["High"] * 4)

	def test_update_route_per_record_docs_keep_working(self):
		frappe.form_dict.docs = [
			{"name": self.names[0], "priority": "Low"},
			{"name": "nope", "priority": "Low"},
		]
		result = bulk_actions.bulk_update_docs("ToDo")
		self.assertEqual(result["done"], [self.names[0]])
		self.assertEqual(result["failed"][0]["name"], "nope")

	def test_delete_route_gives_a_missing_record_a_reason(self):
		frappe.form_dict.names = [self.names[0], "ToDo-gone-47082"]
		frappe.flags.error_message = "No permission for an earlier record"
		result = bulk_actions.bulk_delete_docs("ToDo")
		self.assertEqual(result["done"], [self.names[0]])
		self.assertEqual(result["failed"], [{"name": "ToDo-gone-47082", "error": "Not found"}])

	def test_an_error_without_a_message_still_has_a_reason(self):
		self.assertEqual(bulk.reason_of(frappe.ValidationError()), "Failed without a reason")
		self.assertEqual(bulk.reason_of(frappe.ValidationError("<b>Bad</b> value")), "Bad value")

	def test_update_route_rejects_an_unknown_child_table(self):
		frappe.form_dict.update(names=self.names[:1], child_values={"description": {"x": 1}})
		result = bulk_actions.bulk_update_docs("ToDo")
		self.assertIn("not a table field", result["failed"][0]["error"])

	# bulk_call: an app's whitelisted record function

	STAMP = "frappe.tests.test_bulk_runner.stamp_one"

	def call(self, **body):
		frappe.form_dict.update(names=self.names, **{"method": self.STAMP, **body})
		with self.as_post():
			return bulk_actions.bulk_call_docs("ToDo")

	def as_post(self):
		return patch("frappe.local.request", frappe._dict(method="POST"), create=True)

	def stamped(self, text="stamped") -> list[str]:
		return frappe.get_all("ToDo", {"description": f"{PREFIX} {text}"}, pluck="name")

	def test_call_route_runs_the_method_on_each_record_with_its_args(self):
		result = self.call(args={"text": "hello"})
		self.assertCountEqual(result["done"], self.names)
		self.assertCountEqual(self.stamped("hello"), self.names)

	def test_call_route_keeps_the_methods_messages_out_of_the_response(self):
		self.call()
		self.assertFalse(frappe.local.message_log)

	def test_call_route_refuses_a_function_that_is_not_whitelisted(self):
		with self.assertRaises(frappe.PermissionError):
			self.call(method="frappe.tests.test_bulk_runner.unlisted_one")
		self.assertEqual(self.stamped("unlisted"), [])

	def test_call_route_refuses_a_method_that_does_not_take_post(self):
		with self.assertRaises(frappe.PermissionError):
			self.call(method="frappe.tests.test_bulk_runner.read_only_one")
		self.assertEqual(self.stamped("read only"), [])

	def test_call_route_takes_a_filter_for_the_selection(self):
		frappe.form_dict.update(method=self.STAMP, filters={"description": ["like", f"{PREFIX}%"]})
		with self.as_post():
			result = bulk_actions.bulk_call_docs("ToDo")
		self.assertCountEqual(result["done"], self.names)

	def test_call_route_refuses_a_missing_method(self):
		with self.assertRaises(frappe.ValidationError):
			self.call(method="frappe.tests.test_bulk_runner.nope")

	def test_call_route_validates_its_body(self):
		for body in ({"method": ""}, {"args": ["text"]}, {"args": {"name": "x"}}):
			frappe.form_dict.clear()
			with self.assertRaises(FrappeValueError):
				self.call(**body)

	def test_call_route_fails_a_record_the_method_refuses(self):
		user = self.make_user()
		self.set_gate(user, 1)
		frappe.set_user(user)
		result = self.call()
		self.assertEqual(result["done"], [])
		self.assertEqual(len(result["failed"]), 4)
		self.assertTrue(all(row["error"] for row in result["failed"]))
		self.assertEqual(self.stamped(), [])

	def test_call_route_needs_the_bulk_gate(self):
		user = self.make_user()
		self.set_gate(user, 0)
		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			self.call()

	def test_call_route_refuses_above_the_cap(self):
		with patch.dict(frappe.conf, {"bulk_operation_limit": 2}):
			with self.assertRaises(frappe.ValidationError):
				self.call()
		self.assertEqual(self.stamped(), [])

	def test_call_route_runs_in_the_background_over_the_threshold(self):
		with patch.dict(frappe.conf, {"bulk_operation_async_threshold": 2}):
			with patch("frappe.utils.task_queue.frappe.enqueue") as enqueue:
				response = self.call(args={"text": "later"})
				frappe.db.commit()  # nosemgrep

		self.assertEqual(frappe.response.http_status_code, 202)
		self.assertEqual(self.stamped("later"), [])
		self.assertEqual(
			frappe.db.get_value("Background Task", response["task_id"], "task_name"), "Stamp One ToDo"
		)

		with self.as_post():
			_execute_task(**self.worker_kwargs(enqueue))

		result = frappe.parse_json(frappe.db.get_value("Background Task", response["task_id"], "result"))
		self.assertCountEqual(result["done"], self.names)
		self.assertCountEqual(self.stamped("later"), self.names)

	def touched(self) -> list[str]:
		return frappe.get_all("ToDo", {"description": f"{PREFIX} touched"}, pluck="name")
