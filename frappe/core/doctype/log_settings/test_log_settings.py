# Copyright (c) 2022, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from datetime import datetime

import frappe
from frappe.core.doctype.log_settings.log_settings import (
	_supports_log_clearing,
	get_log_doctypes,
	run_log_clean_up,
)
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime
from frappe.utils.logging import get_log_db


class TestLogSettings(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		frappe.db.set_single_value(
			"Log Settings",
			{
				"clear_error_log_after": 1,
				"clear_activity_log_after": 1,
				"clear_email_queue_after": 1,
			},
		)

	def setUp(self) -> None:
		if self._testMethodName == "test_delete_logs":
			self.datetime = frappe._dict()
			self.datetime.current = now_datetime()
			self.datetime.past = add_to_date(self.datetime.current, days=-4)
			self.log_fixtures = setup_test_logs(self.datetime.past)

	def tearDown(self) -> None:
		if self._testMethodName == "test_delete_logs":
			# The Activity Log and Error Log fixtures live in the log database, which the test
			# runner does not roll back, and retention leaves them alone -- they are only four
			# days old. Without this each run leaves a backdated row behind for the next run to
			# count, and the assertions below fail on any site the suite has run on before.
			log_db = get_log_db()
			for doctype, name in self.log_fixtures.items():
				log_db.delete(doctype, {"name": name})
			log_db.commit()
			del self.log_fixtures
			del self.datetime

	def test_delete_logs(self):
		# make sure test data is present
		activity_log_count = get_log_db().count("Activity Log", {"creation": ("<=", self.datetime.past)})
		error_log_count = get_log_db().count("Error Log", {"creation": ("<=", self.datetime.past)})
		email_queue_count = frappe.db.count("Email Queue", {"creation": ("<=", self.datetime.past)})

		self.assertNotEqual(activity_log_count, 0)
		self.assertNotEqual(error_log_count, 0)
		self.assertNotEqual(email_queue_count, 0)

		# run clean up job
		run_log_clean_up()

		# test if logs are deleted
		activity_log_count = get_log_db().count("Activity Log", {"creation": ("<", self.datetime.past)})
		error_log_count = get_log_db().count("Error Log", {"creation": ("<", self.datetime.past)})
		email_queue_count = frappe.db.count("Email Queue", {"creation": ("<", self.datetime.past)})

		self.assertEqual(activity_log_count, 0)
		self.assertEqual(error_log_count, 0)
		self.assertEqual(email_queue_count, 0)

	def test_logtype_identification(self):
		supported_types = [
			"Error Log",
			"Activity Log",
			"Email Queue",
			"Route History",
			"Scheduled Job Log",
		]

		for lt in supported_types:
			self.assertTrue(_supports_log_clearing(lt), f"{lt} should be recognized as log type")

		unsupported_types = ["DocType", "User", "Non Existing dt"]
		for dt in unsupported_types:
			self.assertFalse(_supports_log_clearing(dt), f"{dt} shouldn't be recognized as log type")

	def test_get_log_doctypes_paging(self):
		log_doctypes = get_log_doctypes("DocType", "", "name", 0, 1000, [])
		self.assertEqual(get_log_doctypes("DocType", "", "name", 2, 2, []), log_doctypes[2:4])


def setup_test_logs(past: datetime) -> dict[str, str]:
	"""Insert one backdated log of each type, and name the ones that need cleaning up."""
	activity_log = frappe.get_doc(
		{
			"doctype": "Activity Log",
			"subject": "Test subject",
			"full_name": "test user2",
		}
	).insert(ignore_permissions=True)
	activity_log.db_set("creation", past)

	error_log = frappe.get_doc(
		{
			"doctype": "Error Log",
			"method": "test_method",
			"error": "traceback",
		}
	).insert(ignore_permissions=True)
	error_log.db_set("creation", past)

	doc1 = frappe.get_doc(
		{
			"doctype": "Email Queue",
			"sender": "test1@example.com",
			"message": "This is a test email1",
			"priority": 1,
			"expose_recipients": "test@receiver.com",
		}
	).insert(ignore_permissions=True)
	doc1.db_set("creation", past)

	# Only the log-database rows are returned: the Email Queue fixtures are in the site
	# database and the test runner rolls those back.
	return {"Activity Log": activity_log.name, "Error Log": error_log.name}
