# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json
from unittest.mock import patch

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.core.doctype.module_def.test_module_def import custom_module
from frappe.desk.desktop import get_desktop_page, update_onboarding_step
from frappe.desk.doctype.sidebar.test_sidebar import no_developer_mode
from frappe.tests import IntegrationTestCase

USER = "test-onboarding@example.com"
ROLE = "Test Onboarding Role"
MODULE = "Test Onboarding Module"


class OnboardingTestCase(IntegrationTestCase):
	"""A role, a one-step onboarding gated to it, and a workspace showing it."""

	def setUp(self):
		# in developer mode each fixture would export itself into the app on disk
		self.enterContext(no_developer_mode())
		self.enterContext(self.change_settings("System Settings", {"enable_onboarding": 1}))
		self.module = self.enterContext(custom_module(MODULE))
		self.role = self.make_role(ROLE)
		self.step = self.make_step("Test Onboarding Step")
		self.onboarding = self.make_onboarding("Test Onboarding", [self.step], roles=[self.role])
		self.workspace = self.make_workspace([self.onboarding])

	def tearDown(self):
		frappe.set_user("Administrator")

	def make_role(self, name: str) -> str:
		if not frappe.db.exists("Role", name):
			frappe.get_doc({"doctype": "Role", "role_name": name}).insert(ignore_permissions=True)
			self.addCleanup(frappe.delete_doc, "Role", name, force=True, ignore_missing=True)
		return name

	def make_user(self, roles: list[str]) -> str:
		frappe.delete_doc("User", USER, force=True, ignore_missing=True)
		frappe.get_doc(
			{
				"doctype": "User",
				"email": USER,
				"first_name": "Onboarding",
				"send_welcome_email": 0,
				"roles": [{"role": role} for role in roles],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "User", USER, force=True, ignore_missing=True)
		return USER

	def make_step(self, title: str, **fields) -> str:
		self.addCleanup(frappe.delete_doc, "Onboarding Step", title, force=True, ignore_missing=True)
		return (
			frappe.get_doc(
				{
					"doctype": "Onboarding Step",
					"__newname": title,
					"title": title,
					"action": "Go to Page",
					"path": "/desk/todo",
					**fields,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def make_onboarding(self, title: str, steps: list[str], roles: list[str], optional=()) -> str:
		self.addCleanup(frappe.delete_doc, "Module Onboarding", title, force=True, ignore_missing=True)
		return (
			frappe.get_doc(
				{
					"doctype": "Module Onboarding",
					"__newname": title,
					"title": title,
					"module": self.module,
					"steps": [{"step": step, "is_optional": int(step in optional)} for step in steps],
					"allow_roles": [{"role": role} for role in roles],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def make_workspace(self, onboardings: list[str]):
		content = [
			{"type": "onboarding", "data": {"onboarding_name": name, "col": 12}} for name in onboardings
		]
		self.addCleanup(
			frappe.delete_doc, "Workspace", "Test Onboarding Workspace", force=True, ignore_missing=True
		)
		return frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": "Test Onboarding Workspace",
				"label": "Test Onboarding Workspace",
				"module": self.module,
				"public": 1,
				"content": json.dumps(content),
			}
		).insert(ignore_permissions=True)

	def onboardings_on_workspace(self) -> list[dict]:
		page = get_desktop_page(json.dumps({"name": self.workspace.name, "title": self.workspace.title}))
		return page["onboardings"]["items"]


class TestWorkspaceOnboarding(OnboardingTestCase):
	"""An onboarding block on a workspace shows its steps to the people the onboarding is for, and
	only they can tick those steps off, since progress is shared by the whole site.
	"""

	def test_a_user_holding_its_role_sees_its_steps(self):
		frappe.set_user(self.make_user(roles=[self.role]))

		(onboarding,) = self.onboardings_on_workspace()
		self.assertEqual(onboarding["label"], self.onboarding)
		self.assertEqual([step.name for step in onboarding["items"]], [self.step])

	def test_a_user_without_its_role_sees_nothing(self):
		frappe.set_user(self.make_user(roles=[self.make_role("Test Other Onboarding Role")]))

		self.assertEqual(self.onboardings_on_workspace(), [])

	def test_a_completed_onboarding_is_not_shown(self):
		frappe.db.set_value("Module Onboarding", self.onboarding, "is_complete", 1)
		frappe.set_user(self.make_user(roles=[self.role]))

		self.assertEqual(self.onboardings_on_workspace(), [])

	def test_a_block_naming_a_missing_onboarding_leaves_the_rest_of_the_workspace(self):
		content = json.loads(self.workspace.content)
		content.insert(0, {"type": "onboarding", "data": {"onboarding_name": "Test Missing Onboarding"}})
		self.workspace.db_set("content", json.dumps(content))
		frappe.set_user(self.make_user(roles=[self.role]))

		self.assertEqual([o["label"] for o in self.onboardings_on_workspace()], [self.onboarding])

	def test_nothing_is_shown_while_onboarding_is_disabled(self):
		self.enterContext(self.change_settings("System Settings", {"enable_onboarding": 0}))
		frappe.set_user(self.make_user(roles=[self.role]))

		self.assertEqual(self.onboardings_on_workspace(), [])

	def test_a_user_holding_its_role_can_complete_a_step(self):
		frappe.set_user(self.make_user(roles=[self.role]))

		update_onboarding_step(self.step, "is_complete", 1)
		self.assertEqual(frappe.db.get_value("Onboarding Step", self.step, "is_complete"), 1)

	def test_a_user_without_its_role_cannot_complete_or_skip_a_step(self):
		frappe.set_user(self.make_user(roles=[self.make_role("Test Other Onboarding Role")]))

		for field in ("is_complete", "is_skipped"):
			with self.assertRaises(frappe.PermissionError):
				update_onboarding_step(self.step, field, 1)
		self.assertEqual(
			frappe.db.get_value("Onboarding Step", self.step, ["is_complete", "is_skipped"]), (0, 0)
		)

	def test_only_the_people_an_onboarding_is_for_can_read_its_steps(self):
		"""A step's status says whether its work is done anywhere on the site, so it is not for
		everyone who can log in."""
		from frappe.desk.doctype.onboarding_step.onboarding_step import get_onboarding_steps

		frappe.set_user(self.make_user(roles=[self.make_role("Test Other Onboarding Role")]))
		with self.assertRaises(frappe.PermissionError):
			get_onboarding_steps([{"step": self.step}])

		frappe.set_user("Administrator")
		frappe.set_user(self.make_user(roles=[self.role]))
		self.assertEqual([s.name for s in get_onboarding_steps([{"step": self.step}])], [self.step])

	def test_a_step_no_onboarding_uses_cannot_be_marked(self):
		orphan = self.make_step("Test Orphan Onboarding Step")
		frappe.set_user(self.make_user(roles=[self.role]))

		with self.assertRaises(frappe.PermissionError):
			update_onboarding_step(orphan, "is_complete", 1)

	def test_only_the_progress_fields_can_be_changed(self):
		frappe.set_user(self.make_user(roles=[self.role]))

		update_onboarding_step(self.step, "title", "Renamed")
		self.assertEqual(frappe.db.get_value("Onboarding Step", self.step, "title"), "Test Onboarding Step")


class TestStepCompletion(OnboardingTestCase):
	"""A step that asks for something the site can show, a record or a setting, is done when that
	thing is, and an onboarding is done the moment its last step is.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.record_doctype = new_doctype(custom=1).insert(ignore_permissions=True).name
		cls.submittable_doctype = new_doctype(custom=1, is_submittable=1).insert(ignore_permissions=True).name

	@classmethod
	def tearDownClass(cls):
		# Committed fixtures cannot be removed by the test framework's rollback.
		for doctype in (cls.record_doctype, cls.submittable_doctype):
			frappe.delete_doc("DocType", doctype, force=True, ignore_missing=True)
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def make_record(self, doctype: str, submit: bool = False):
		doc = frappe.get_doc({"doctype": doctype, "some_fieldname": "example"})
		doc.flags.ignore_permissions = True
		doc.insert()
		self.addCleanup(frappe.delete_doc, doctype, doc.name, force=True, ignore_missing=True)
		if submit:
			doc.submit()
			# a submitted record has to be cancelled before it can be deleted
			self.addCleanup(doc.cancel)
		return doc

	def onboarding_with(self, *steps: str, optional=()) -> str:
		frappe.delete_doc("Module Onboarding", "Test Completion Onboarding", force=True, ignore_missing=True)
		return self.make_onboarding(
			"Test Completion Onboarding", list(steps), roles=[self.role], optional=optional
		)

	def is_complete(self, doctype: str, name: str) -> int:
		return frappe.db.get_value(doctype, name, "is_complete")

	def test_a_create_step_is_not_done_until_a_record_exists(self):
		step = self.make_step(
			"Test Create Step", action="Create Entry", reference_document=self.record_doctype
		)
		self.onboarding_with(step)
		frappe.set_user(self.make_user(roles=[self.role]))

		with self.assertRaises(frappe.ValidationError):
			update_onboarding_step(step, "is_complete", 1)

		frappe.set_user("Administrator")
		self.make_record(self.record_doctype)
		frappe.set_user(USER)

		update_onboarding_step(step, "is_complete", 1)
		self.assertEqual(self.is_complete("Onboarding Step", step), 1)

	def test_a_step_for_a_submittable_record_needs_a_submitted_one(self):
		step = self.make_step(
			"Test Submit Step", action="Create Entry", reference_document=self.submittable_doctype
		)
		self.onboarding_with(step)
		self.make_record(self.submittable_doctype)
		frappe.set_user(self.make_user(roles=[self.role]))

		with self.assertRaises(frappe.ValidationError):
			update_onboarding_step(step, "is_complete", 1)

		frappe.set_user("Administrator")
		self.make_record(self.submittable_doctype, submit=True)
		frappe.set_user(USER)

		update_onboarding_step(step, "is_complete", 1)
		self.assertEqual(self.is_complete("Onboarding Step", step), 1)

	def test_a_record_made_elsewhere_shows_its_step_done(self):
		"""The setup wizard makes a Company and an import makes Customers; nobody should be asked to
		create what is already there."""
		step = self.make_step(
			"Test Existing Step", action="Create Entry", reference_document=self.record_doctype
		)
		self.make_record(self.record_doctype)
		# a second, open step, since an onboarding with every step done is not shown at all
		onboarding = self.onboarding_with(step, self.make_step("Test Open Step"))
		self.workspace.db_set(
			"content", json.dumps([{"type": "onboarding", "data": {"onboarding_name": onboarding}}])
		)
		frappe.set_user(self.make_user(roles=[self.role]))

		(shown,) = self.onboardings_on_workspace()
		self.assertEqual([s.is_complete for s in shown["items"]], [1, 0])

	def test_a_settings_step_checks_the_saved_value(self):
		self.enterContext(self.change_settings("System Settings", {"hide_footer_in_auto_email_reports": 0}))
		step = self.make_step(
			"Test Settings Step",
			action="Update Settings",
			reference_document="System Settings",
			field="hide_footer_in_auto_email_reports",
			value_to_validate="1",
			validate_action=1,
		)
		self.onboarding_with(step)
		frappe.set_user(self.make_user(roles=[self.role]))

		with self.assertRaises(frappe.ValidationError):
			update_onboarding_step(step, "is_complete", 1)

		frappe.set_user("Administrator")
		self.enterContext(self.change_settings("System Settings", {"hide_footer_in_auto_email_reports": 1}))
		frappe.set_user(USER)

		update_onboarding_step(step, "is_complete", 1)
		self.assertEqual(self.is_complete("Onboarding Step", step), 1)

	def test_the_onboarding_is_done_with_its_last_step(self):
		first = self.make_step("Test First Step")
		second = self.make_step("Test Second Step")
		onboarding = self.onboarding_with(first, second)
		frappe.set_user(self.make_user(roles=[self.role]))

		update_onboarding_step(first, "is_complete", 1)
		self.assertEqual(self.is_complete("Module Onboarding", onboarding), 0)

		update_onboarding_step(second, "is_skipped", 1)
		self.assertEqual(self.is_complete("Module Onboarding", onboarding), 1)

	def test_bringing_back_a_skipped_step_reopens_the_onboarding(self):
		step = self.make_step("Test Skipped Step")
		onboarding = self.onboarding_with(step)
		frappe.set_user(self.make_user(roles=[self.role]))

		update_onboarding_step(step, "is_skipped", 1)
		self.assertEqual(self.is_complete("Module Onboarding", onboarding), 1)

		update_onboarding_step(step, "is_skipped", 0)
		self.assertEqual(self.is_complete("Module Onboarding", onboarding), 0)

	def test_users_the_system_made_do_not_finish_an_invite_step(self):
		"""Administrator and Guest exist on every site, so they cannot count as an invited team."""
		step = self.make_step("Test Invite Step", action="Create Entry", reference_document="User")
		onboarding = self.onboarding_with(step, self.make_step("Test Open Step"))
		self.workspace.db_set(
			"content", json.dumps([{"type": "onboarding", "data": {"onboarding_name": onboarding}}])
		)
		frappe.set_user(self.make_user(roles=[self.role]))

		(shown,) = self.onboardings_on_workspace()
		self.assertEqual([s.is_complete for s in shown["items"]], [0, 0])

	def test_a_step_counts_only_records_matching_its_defaults(self):
		"""Steps that create the same doctype differ only in the defaults they open the record with,
		so one record must not finish them all."""
		self.make_record(self.record_doctype)  # some_fieldname = "example"
		matching = self.make_step(
			"Test Matching Step",
			action="Create Entry",
			reference_document=self.record_doctype,
			route_options='{"some_fieldname": "example", "not_a_field": "ignored"}',
		)
		other = self.make_step(
			"Test Other Step",
			action="Create Entry",
			reference_document=self.record_doctype,
			route_options='{"some_fieldname": "something else"}',
		)

		self.assertTrue(frappe.get_doc("Onboarding Step", matching).is_work_done())
		self.assertFalse(frappe.get_doc("Onboarding Step", other).is_work_done())

	def test_import_is_offered_for_records_the_user_may_import(self):
		"""Masters arrive as lists; a transaction is made one at a time; and only someone allowed to
		import the doctype is offered to. Email Group allows import, for Newsletter Managers."""
		from frappe.desk.doctype.onboarding_step.onboarding_step import get_step_details

		master = self.make_step("Test Import Step", action="Create Entry", reference_document="Email Group")
		transaction = self.make_step(
			"Test Transaction Step", action="Create Entry", reference_document=self.submittable_doctype
		)

		frappe.set_user(self.make_user(roles=["Newsletter Manager"]))
		self.assertTrue(get_step_details(master).can_import)
		self.assertFalse(get_step_details(transaction).can_import)

		frappe.set_user("Administrator")
		frappe.set_user(self.make_user(roles=[self.role]))
		self.assertFalse(get_step_details(master).can_import)

	def test_optional_steps_do_not_hold_up_the_onboarding(self):
		"""They show what else the module can do; finishing the required ones finishes it."""
		required = self.make_step("Test Required Step")
		optional = self.make_step("Test Optional Step")
		onboarding = self.onboarding_with(required, optional, optional=[optional])
		frappe.set_user(self.make_user(roles=[self.role]))

		update_onboarding_step(required, "is_complete", 1)
		self.assertEqual(self.is_complete("Module Onboarding", onboarding), 1)

	def test_a_step_is_optional_in_one_onboarding_and_required_in_another(self):
		"""Optional belongs to the onboarding's row, so a shared step keeps both answers."""
		shared = self.make_step("Test Shared Step")
		open_step = self.make_step("Test Open Step")
		onboarding = self.onboarding_with(shared, open_step, optional=[shared])
		self.workspace.db_set(
			"content", json.dumps([{"type": "onboarding", "data": {"onboarding_name": onboarding}}])
		)
		frappe.set_user(self.make_user(roles=[self.role]))

		(shown,) = self.onboardings_on_workspace()
		self.assertEqual([s.is_optional for s in shown["items"]], [1, 0])

	def test_a_step_leading_to_an_onboarding_is_done_when_that_onboarding_is(self):
		"""A front-door onboarding has a step per module, each done when the module's own is."""
		from frappe.desk.doctype.onboarding_step.onboarding_step import get_step_details

		create = self.make_step(
			"Test Create Record Step", action="Create Entry", reference_document=self.record_doctype
		)
		optional = self.make_step("Test Optional Step")
		module_onboarding = self.make_onboarding(
			"Test Module Onboarding", [create, optional], roles=[self.role], optional=[optional]
		)
		lead = self.make_step(
			"Test Lead Step", action="Complete Onboarding", module_onboarding=module_onboarding
		)
		self.onboarding_with(lead)
		frappe.set_user(self.make_user(roles=[self.role]))

		self.assertEqual(get_step_details(lead).module, self.module)
		self.assertFalse(get_step_details(lead).is_complete)
		with self.assertRaisesRegex(frappe.ValidationError, "Finish Test Module Onboarding"):
			update_onboarding_step(lead, "is_complete", 1)

		self.make_record(self.record_doctype)
		self.assertTrue(get_step_details(lead).is_complete)

	def test_onboardings_leading_to_each_other_do_not_loop(self):
		"""Each reads the other one level deep, by whether its step there is ticked off."""
		from frappe.desk.doctype.onboarding_step.onboarding_step import get_step_details

		first = self.make_onboarding("Test First Onboarding", [self.step], roles=[self.role])
		second = self.make_onboarding("Test Second Onboarding", [self.step], roles=[self.role])
		to_second = self.make_step(
			"Test To Second Step", action="Complete Onboarding", module_onboarding=second
		)
		to_first = self.make_step("Test To First Step", action="Complete Onboarding", module_onboarding=first)
		for onboarding, step in ((first, to_second), (second, to_first)):
			doc = frappe.get_doc("Module Onboarding", onboarding)
			doc.steps = []
			doc.append("steps", {"step": step})
			doc.save(ignore_permissions=True)

		self.assertFalse(get_step_details(to_second).is_complete)

		frappe.db.set_value("Onboarding Step", to_first, "is_skipped", 1)
		self.assertTrue(get_step_details(to_second).is_complete)


class TestOnboardingTelemetry(OnboardingTestCase):
	"""Telemetry names what happened and carries the step and its onboarding as properties, so one
	funnel per onboarding can follow its steps.
	"""

	def captured(self, field: str, value: int) -> list:
		with patch("frappe.desk.doctype.module_onboarding.module_onboarding.capture") as capture:
			update_onboarding_step(self.step, field, value)
		return [(call.args[0], call.kwargs["properties"]) for call in capture.call_args_list]

	def test_ticking_off_the_last_step_reports_the_step_then_the_onboarding(self):
		frappe.set_user(self.make_user(roles=[self.role]))

		self.assertEqual(
			self.captured("is_complete", 1),
			[
				(
					"step_completed",
					{"step": self.step, "action": "Go to Page", "onboardings": [self.onboarding]},
				),
				("onboarding_completed", {"onboarding": self.onboarding, "module": self.module}),
			],
		)

	def test_skipping_and_bringing_back_a_step_are_reported(self):
		second = self.make_step("Test Second Telemetry Step")
		onboarding = frappe.get_doc("Module Onboarding", self.onboarding)
		onboarding.append("steps", {"step": second})
		onboarding.save(ignore_permissions=True)
		frappe.set_user(self.make_user(roles=[self.role]))

		self.assertEqual([event for event, _ in self.captured("is_skipped", 1)], ["step_skipped"])
		self.assertEqual([event for event, _ in self.captured("is_skipped", 0)], ["step_reopened"])
