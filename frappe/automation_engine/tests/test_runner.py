# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.automation_engine.actions.base import AutomationAction, get_action_registry
from frappe.automation_engine.registry import clear_automation_cache
from frappe.automation_engine.runner import (
	TASK_METHOD,
	_failure_key,
	automation_task_name,
	execute_automation,
)
from frappe.tests import IntegrationTestCase

QUEUE = "Automation Trigger Queue"


def set_field(field, value):
	return {"action_type": "SetFieldValue", "params": json.dumps({"field": field, "value": value})}


def make_todo(**kwargs):
	return frappe.get_doc({"doctype": "ToDo", "description": "x", **kwargs}).insert()


def make_automation(actions, stop_on_error=1, **kwargs):
	doc = frappe.new_doc("Automation Flow")
	doc.title = "Runner Rule"
	doc.trigger_type = kwargs.pop("trigger_type", "Doc Created")
	doc.document_type = kwargs.pop("document_type", "ToDo")
	doc.stop_on_error = stop_on_error
	for key, value in kwargs.items():
		doc.set(key, value)
	for action in actions:
		doc.append("actions", action)
	doc.enabled = 1
	doc.insert()
	return doc.name


def make_broken_automation(stop_on_error=1):
	"""A rule whose action_type no longer resolves (e.g. its action was removed post-save)."""
	auto = make_automation([set_field("priority", "Low")], stop_on_error=stop_on_error)
	set_first_action_type(auto, "NopeAction")
	return auto


def set_first_action_type(auto, action_type):
	child = frappe.db.get_value("Automation Action", {"parent": auto}, "name")
	frappe.db.set_value("Automation Action", child, "action_type", action_type, update_modified=False)
	frappe.clear_document_cache("Automation Flow", auto)


class AutomationRunnerTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.local.automation_actions = None
		clear_automation_cache()

	def tearDown(self):
		frappe.db.rollback()
		frappe.local.automation_actions = None
		clear_automation_cache()

	def queue_row(self, automation, ref_name, depth=1, ref_doctype="ToDo", payload=None):
		row = frappe.get_doc(
			{
				"doctype": QUEUE,
				"automation": automation,
				"ref_doctype": ref_doctype,
				"ref_name": ref_name,
				"status": "Pending",
				"triggered_at": frappe.utils.now(),
				"depth": depth,
				"event_payload": json.dumps(payload) if payload else None,
			}
		).insert(ignore_permissions=True)
		return row.name

	def run_status(self, automation):
		return self.run_result(automation)["automation_status"]

	def run_result(self, automation):
		result = frappe.get_all(
			"Background Task",
			filters={"task_name": automation_task_name(automation), "method": TASK_METHOD},
			pluck="result",
		)[0]
		return json.loads(result)


class TestRunner(AutomationRunnerTestCase):
	def test_success_applies_action_and_deletes_queue_row(self):
		todo = make_todo()
		auto = make_automation([set_field("priority", "High")])
		name = self.queue_row(auto, todo.name)
		execute_automation(name)
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "High")
		self.assertFalse(frappe.db.exists(QUEUE, name))
		self.assertEqual(self.run_status(auto), "Success")
		result = self.run_result(auto)
		self.assertEqual(result["steps"][0]["status"], "Success")
		arguments = frappe.db.get_value(
			"Background Task", {"task_name": automation_task_name(auto)}, "arguments"
		)
		self.assertEqual(json.loads(arguments)["actions_snapshot"][0]["action_type"], "SetFieldValue")

	def test_missing_target_is_skipped(self):
		auto = make_automation([set_field("priority", "High")])
		name = self.queue_row(auto, "NO-SUCH-TODO")
		execute_automation(name)
		self.assertEqual(self.run_status(auto), "Skipped")
		self.assertEqual(frappe.db.get_value(QUEUE, name, "status"), "Skipped")

	def test_docless_run_executes_with_payload_context(self):
		auto = make_automation(
			[
				{
					"action_type": "CreateDocument",
					"params": json.dumps(
						{"doctype": "ToDo", "values": {"description": "weekly-{{ payload.label }}"}}
					),
				}
			],
			trigger_type="Scheduled",
			document_type=None,
			cron_expression="0 0 * * *",
		)
		name = self.queue_row(auto, None, ref_doctype=None, payload={"label": "digest"})
		execute_automation(name)
		self.assertEqual(self.run_status(auto), "Success")
		self.assertTrue(frappe.db.exists("ToDo", {"description": "weekly-digest"}))

	def test_failed_action_stops_and_marks_failed(self):
		todo = make_todo()
		auto = make_broken_automation(stop_on_error=1)
		name = self.queue_row(auto, todo.name)
		execute_automation(name)
		self.assertEqual(self.run_status(auto), "Failed")
		self.assertEqual(frappe.db.get_value(QUEUE, name, "status"), "Failed")

	def test_partial_failure_continues_when_not_stopping(self):
		todo = make_todo()
		auto = make_automation([set_field("priority", "Low"), set_field("priority", "High")], stop_on_error=0)
		first_child = frappe.get_all("Automation Action", filters={"parent": auto}, order_by="idx", limit=1)[
			0
		].name
		frappe.db.set_value(
			"Automation Action", first_child, "action_type", "NopeAction", update_modified=False
		)
		frappe.clear_document_cache("Automation Flow", auto)
		name = self.queue_row(auto, todo.name)
		execute_automation(name)
		self.assertEqual(self.run_status(auto), "Partially Failed")
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "High")
		self.assertFalse(frappe.db.exists(QUEUE, name))

	def test_step_condition_false_skips_action(self):
		todo = make_todo(priority="Low")
		auto = make_automation(
			[
				{
					"action_type": "SetFieldValue",
					"params": json.dumps({"field": "priority", "value": "High"}),
					"step_condition": "doc.priority == 'Medium'",
				}
			]
		)
		execute_automation(self.queue_row(auto, todo.name))
		self.assertEqual(self.run_status(auto), "Success")
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "Low")

	def test_savepoint_rolls_back_failed_action_writes(self):
		class Boom(AutomationAction):
			action_type = "BoomAction"

			def execute(self, doc, params, context):
				frappe.get_doc({"doctype": "ToDo", "description": "ghost-savepoint"}).insert(
					ignore_permissions=True
				)
				raise Exception("boom")

		frappe.local.automation_actions = {**get_action_registry(), "BoomAction": Boom()}
		todo = make_todo()
		auto = make_automation([set_field("priority", "Low")], stop_on_error=1)
		set_first_action_type(auto, "BoomAction")
		name = self.queue_row(auto, todo.name)
		execute_automation(name)
		self.assertEqual(self.run_status(auto), "Failed")
		self.assertFalse(frappe.db.exists("ToDo", {"description": "ghost-savepoint"}))

	def test_timestamp_mismatch_retries_and_recovers(self):
		class Racy(AutomationAction):
			action_type = "RacyAction"
			calls = 0

			def execute(self, doc, params, context):
				Racy.calls += 1
				if Racy.calls == 1:
					# Make the in-memory doc stale so the first save raises TimestampMismatch.
					newer = frappe.utils.add_to_date(frappe.utils.now(), days=1)
					frappe.db.set_value("ToDo", doc.name, "modified", newer, update_modified=False)
				doc.set("priority", "High")
				doc.save(ignore_permissions=True)
				return "ok"

		frappe.local.automation_actions = {**get_action_registry(), "RacyAction": Racy()}
		todo = make_todo()
		auto = make_automation([set_field("priority", "Low")])
		set_first_action_type(auto, "RacyAction")
		execute_automation(self.queue_row(auto, todo.name))
		self.assertEqual(self.run_status(auto), "Success")
		self.assertGreaterEqual(Racy.calls, 2)

	def test_triggering_user_is_recorded_as_execution_identity(self):
		user = frappe.get_doc(
			{"doctype": "User", "email": "automation-trigger@example.com", "first_name": "Trigger"}
		).insert(ignore_permissions=True)
		todo = make_todo()
		auto = make_automation([set_field("priority", "High")], run_as="Triggering User")
		row = self.queue_row(auto, todo.name)
		frappe.db.set_value(QUEUE, row, "triggered_by", user.name, update_modified=False)
		execute_automation(row)
		run_user = frappe.db.get_value("Background Task", {"task_name": automation_task_name(auto)}, "user")
		self.assertEqual(run_user, user.name)

	def test_breaker_skips_pending_backlog(self):
		todo = make_todo()
		auto = make_broken_automation(stop_on_error=1)
		frappe.cache.delete(_failure_key(auto))
		original = frappe.conf.get("automation_failure_threshold")
		frappe.conf.automation_failure_threshold = 1
		try:
			backlog = [self.queue_row(auto, f"OTHER-{i}") for i in range(2)]
			execute_automation(self.queue_row(auto, todo.name))
			for name in backlog:
				self.assertEqual(frappe.db.get_value(QUEUE, name, "status"), "Skipped")
		finally:
			frappe.conf.automation_failure_threshold = original
			frappe.cache.delete(_failure_key(auto))

	def test_circuit_breaker_disables_after_threshold(self):
		todo = make_todo()
		auto = make_broken_automation(stop_on_error=1)
		frappe.cache.delete(_failure_key(auto))
		original = frappe.conf.get("automation_failure_threshold")
		frappe.conf.automation_failure_threshold = 2
		try:
			for _ in range(2):
				execute_automation(self.queue_row(auto, todo.name))
			self.assertEqual(frappe.db.get_value("Automation Flow", auto, "enabled"), 0)
			self.assertTrue(frappe.db.get_value("Automation Flow", auto, "disabled_reason"))
		finally:
			frappe.conf.automation_failure_threshold = original
			frappe.cache.delete(_failure_key(auto))


def branch(action, parent_step, arm):
	return {**action, "parent_step": parent_step, "branch": arm}


def wait(value, unit="Seconds"):
	return {"step_type": "Wait", "params": json.dumps({"value": value, "unit": unit})}


def if_step(condition):
	return {"step_type": "If", "step_condition": condition}


class TestBranching(AutomationRunnerTestCase):
	def branching_rule(self):
		"""High priority takes the If arm, anything else the Else arm."""
		return make_automation(
			[
				if_step("doc.priority == 'High'"),
				branch(set_field("status", "Closed"), 1, "If"),
				branch(set_field("status", "Cancelled"), 1, "Else"),
				set_field("description", "after"),
			]
		)

	def test_if_arm_runs_and_else_arm_is_untouched(self):
		todo = make_todo(priority="High")
		auto = self.branching_rule()
		execute_automation(self.queue_row(auto, todo.name))
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "status"), "Closed")
		self.assertEqual(self.run_status(auto), "Success")

	def test_else_arm_runs_when_condition_is_false(self):
		todo = make_todo(priority="Low")
		auto = self.branching_rule()
		execute_automation(self.queue_row(auto, todo.name))
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "status"), "Cancelled")

	def test_untaken_arm_is_not_logged_as_a_step(self):
		todo = make_todo(priority="High")
		auto = self.branching_rule()
		execute_automation(self.queue_row(auto, todo.name))
		positions = [step["step_idx"] for step in self.run_result(auto)["steps"]]
		self.assertEqual(positions, [0, 1, 3])  # the Else arm at position 2 never ran

	def test_steps_after_the_branch_still_run(self):
		todo = make_todo(priority="Low")
		auto = self.branching_rule()
		execute_automation(self.queue_row(auto, todo.name))
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "description"), "after")

	def test_nested_if_only_runs_on_the_taken_outer_arm(self):
		todo = make_todo(priority="High", status="Open")
		auto = make_automation(
			[
				if_step("doc.priority == 'Low'"),
				branch(if_step("True"), 1, "If"),
				branch(set_field("description", "nested-ran"), 2, "If"),
				branch(set_field("description", "outer-else"), 1, "Else"),
			]
		)
		execute_automation(self.queue_row(auto, todo.name))
		# The inner If sits on the outer Else arm, so neither it nor its child may run.
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "description"), "outer-else")


class TestWaitResume(AutomationRunnerTestCase):
	def wait_rule(self, seconds=5):
		return make_automation([set_field("priority", "High"), wait(seconds), set_field("status", "Closed")])

	def resume_row(self, automation):
		return frappe.db.get_value(
			QUEUE, {"automation": automation, "resume_run": ("is", "set")}, ["name", "resume_from_idx"]
		)

	def test_wait_pauses_the_run_and_queues_a_resume_row(self):
		todo = make_todo()
		auto = self.wait_rule()
		execute_automation(self.queue_row(auto, todo.name))

		self.assertEqual(self.run_status(auto), "Waiting")
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "High")
		self.assertNotEqual(frappe.db.get_value("ToDo", todo.name, "status"), "Closed")
		name, resume_from_idx = self.resume_row(auto)
		self.assertEqual(resume_from_idx, 2)
		self.assertTrue(frappe.db.get_value(QUEUE, name, "run_after"))

	def test_waiting_task_stays_running_until_it_resumes(self):
		todo = make_todo()
		auto = self.wait_rule()
		execute_automation(self.queue_row(auto, todo.name))
		task = frappe.db.get_value(
			"Background Task", {"task_name": automation_task_name(auto)}, ["status", "ended_at"]
		)
		self.assertEqual(task[0], "Running")
		self.assertIsNone(task[1])

	def test_resume_finishes_the_same_task(self):
		todo = make_todo()
		auto = self.wait_rule()
		execute_automation(self.queue_row(auto, todo.name))
		before = frappe.get_all("Background Task", filters={"task_name": automation_task_name(auto)})

		# The drainer would pick this up once run_after passes; call it directly.
		execute_automation(self.resume_row(auto)[0])

		after = frappe.get_all("Background Task", filters={"task_name": automation_task_name(auto)})
		self.assertEqual(len(before), len(after))
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "status"), "Closed")
		self.assertEqual(self.run_status(auto), "Success")

	def test_resume_does_not_re_execute_steps_from_before_the_wait(self):
		todo = make_todo()
		auto = self.wait_rule()
		execute_automation(self.queue_row(auto, todo.name))
		frappe.db.set_value("ToDo", todo.name, "priority", "Low", update_modified=False)

		execute_automation(self.resume_row(auto)[0])

		# Step 0 ran in the first leg; a resumed run must not set priority back to High.
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "Low")

	def test_resumed_run_keeps_the_steps_from_the_first_leg(self):
		todo = make_todo()
		auto = self.wait_rule()
		execute_automation(self.queue_row(auto, todo.name))
		execute_automation(self.resume_row(auto)[0])
		positions = [step["step_idx"] for step in self.run_result(auto)["steps"]]
		self.assertEqual(positions, [0, 1, 2])

	def test_resume_runs_the_snapshot_not_the_edited_rule(self):
		todo = make_todo()
		auto = self.wait_rule()
		execute_automation(self.queue_row(auto, todo.name))

		# Rewrite the rule mid-wait: the resumed leg must still use the original plan.
		rule = frappe.get_doc("Automation Flow", auto)
		rule.actions[2].params = json.dumps({"field": "status", "value": "Cancelled"})
		rule.save()

		execute_automation(self.resume_row(auto)[0])
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "status"), "Closed")

	def test_target_deleted_during_the_wait_is_skipped(self):
		todo = make_todo()
		auto = self.wait_rule()
		execute_automation(self.queue_row(auto, todo.name))
		resume = self.resume_row(auto)[0]
		frappe.delete_doc("ToDo", todo.name, force=True, ignore_permissions=True)

		execute_automation(resume)
		self.assertEqual(self.run_status(auto), "Skipped")

	def test_wait_inside_a_branch_resumes_on_the_same_arm(self):
		todo = make_todo(priority="High")
		auto = make_automation(
			[
				if_step("doc.priority == 'High'"),
				branch(wait(5), 1, "If"),
				branch(set_field("status", "Closed"), 1, "If"),
				branch(set_field("status", "Cancelled"), 1, "Else"),
			]
		)
		execute_automation(self.queue_row(auto, todo.name))
		self.assertEqual(self.run_status(auto), "Waiting")

		execute_automation(self.resume_row(auto)[0])
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "status"), "Closed")

	def test_branch_taken_before_a_wait_survives_the_document_changing(self):
		# The arm is a decision the first leg made. If the resumed leg re-derives it against
		# the document as it is now, a change during the wait strands the arm it committed to
		# and starts running steps from the arm it never entered.
		todo = make_todo(priority="High")
		auto = make_automation(
			[
				if_step("doc.priority == 'High'"),
				branch(wait(5), 1, "If"),
				branch(set_field("status", "Closed"), 1, "If"),
				branch(set_field("status", "Cancelled"), 1, "Else"),
			]
		)
		execute_automation(self.queue_row(auto, todo.name))
		frappe.db.set_value("ToDo", todo.name, "priority", "Low", update_modified=False)

		execute_automation(self.resume_row(auto)[0])

		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "status"), "Closed")

	def test_branch_arms_are_recorded_on_the_run(self):
		todo = make_todo(priority="High")
		auto = make_automation([if_step("doc.priority == 'High'"), branch(wait(5), 1, "If")])
		execute_automation(self.queue_row(auto, todo.name))
		self.assertEqual(self.run_result(auto)["branches"], {"1": "If"})
