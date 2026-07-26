# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.core.doctype.scheduled_job_type.scheduled_job_type import sync_jobs
from frappe.tests import IntegrationTestCase
from frappe.utils import get_datetime
from frappe.utils.data import add_to_date, now_datetime


def raise_import_error(doc, method=None):
	raise ImportError("cannot import name '_follow_document' from 'frappe.desk.form.document_follow'")


def record_job_run():
	frappe.flags.scheduled_job_ran = True


def delete_scheduled_job(name):
	frappe.delete_doc("Scheduled Job Type", name, force=True, ignore_missing=True)
	frappe.db.commit()  # nosemgrep


class TestScheduledJobType(IntegrationTestCase):
	def setUp(self):
		frappe.db.rollback()
		frappe.db.truncate("Scheduled Job Type")
		sync_jobs()
		frappe.db.commit()  # nosemgrep

	def test_throws_on_duplicate_job(self):
		job_config = dict(
			doctype="Scheduled Job Type",
			method="frappe.desk.notifications.clear_notifications",
			frequency="Weekly",
		)
		frappe.get_doc(job_config).insert()

		duplicate_job = frappe.get_doc(job_config)

		self.assertRaises(Exception, duplicate_job.insert)
		frappe.db.rollback()

	def test_throws_on_duplicate_job_with_cron_format(self):
		job_config = dict(
			doctype="Scheduled Job Type",
			method="frappe.desk.notifications.clear_notifications",
			frequency="Cron",
			cron_format="*/1 * * * *",
		)
		frappe.get_doc(job_config).insert()

		duplicate_job = frappe.get_doc(job_config)

		self.assertRaises(Exception, duplicate_job.insert)
		frappe.db.rollback()

	def test_sync_jobs(self):
		all_job = frappe.get_doc("Scheduled Job Type", dict(method="frappe.email.queue.flush"))
		self.assertEqual(all_job.frequency, "All")

		daily_job = frappe.get_doc(
			"Scheduled Job Type", dict(method="frappe.desk.notifications.clear_notifications")
		)
		self.assertEqual(daily_job.frequency, "Daily Maintenance")

		# check if cron jobs are synced
		cron_job = frappe.get_doc("Scheduled Job Type", dict(method="frappe.deferred_insert.save_to_db"))
		self.assertEqual(cron_job.frequency, "Cron")
		self.assertEqual(cron_job.cron_format, "0/15 * * * *")

		# check if jobs are synced after change in hooks
		updated_scheduler_events = {"hourly": ["frappe.email.queue.flush"]}
		sync_jobs(updated_scheduler_events)
		updated_scheduled_job = frappe.get_doc("Scheduled Job Type", {"method": "frappe.email.queue.flush"})
		self.assertEqual(updated_scheduled_job.frequency, "Hourly")

	def test_daily_job(self):
		job = frappe.get_doc(
			"Scheduled Job Type",
			dict(method="frappe.email.doctype.notification.notification.trigger_daily_alerts"),
		)
		job.db_set("last_execution", "2019-01-01 00:00:00")
		self.assertTrue(job.is_event_due(get_datetime("2019-01-02 00:00:06")))
		self.assertFalse(job.is_event_due(get_datetime("2019-01-01 00:00:06")))
		self.assertFalse(job.is_event_due(get_datetime("2019-01-01 23:59:59")))

	def test_weekly_job(self):
		job = frappe.get_doc(
			"Scheduled Job Type",
			dict(method="frappe.desk.form.document_follow.send_weekly_updates"),
		)
		job.db_set("last_execution", "2019-01-01 00:00:00")
		self.assertTrue(job.is_event_due(get_datetime("2019-01-06 00:10:01")))  # +10 min because of jitter
		self.assertFalse(job.is_event_due(get_datetime("2019-01-02 00:00:06")))
		self.assertFalse(job.is_event_due(get_datetime("2019-01-05 23:59:59")))

	def test_monthly_job(self):
		job = frappe.get_doc(
			"Scheduled Job Type",
			dict(method="frappe.email.doctype.auto_email_report.auto_email_report.send_monthly"),
		)
		job.db_set("last_execution", "2019-01-01 00:00:00")
		self.assertTrue(job.is_event_due(get_datetime("2019-02-01 00:00:01")))
		self.assertFalse(job.is_event_due(get_datetime("2019-01-15 00:00:06")))
		self.assertFalse(job.is_event_due(get_datetime("2019-01-31 23:59:59")))

	def test_cron_job(self):
		# runs every 10 mins
		job = frappe.get_doc(
			"Scheduled Job Type", dict(method="frappe.email.doctype.email_account.email_account.pull")
		)
		job.db_set("last_execution", "2019-01-01 00:00:00")
		self.assertEqual(job.next_execution, get_datetime("2019-01-01 00:10:00"))
		self.assertTrue(job.is_event_due(get_datetime("2019-01-01 00:10:01")))
		self.assertFalse(job.is_event_due(get_datetime("2019-01-01 00:05:06")))
		self.assertFalse(job.is_event_due(get_datetime("2019-01-01 00:09:59")))

	def test_maintenance_jobs(self):
		sjt = frappe.new_doc(
			"Scheduled Job Type",
			frequency="Hourly Maintenance",
			last_execution=get_datetime("2019-01-01 23:59:00"),
		)
		# "maintenance.test" offset is 38 minutes
		with patch.object(frappe.local, "site", "maintenance.test"):
			self.assertEqual(sjt.next_execution, get_datetime("2019-01-02 00:38:00"))

		# Should be within one hour
		self.assertGreaterEqual(sjt.next_execution, sjt.last_execution)
		self.assertGreaterEqual(add_to_date(sjt.last_execution, hours=1), sjt.next_execution)

		# Next should be exactly one hour away
		sjt.last_execution = sjt.next_execution
		self.assertEqual(add_to_date(sjt.last_execution, hours=1), sjt.next_execution)

	def test_job_survives_failing_log(self):
		job = frappe.get_doc(
			doctype="Scheduled Job Type",
			method="frappe.core.doctype.scheduled_job_type.test_scheduled_job_type.record_job_run",
			frequency="Daily",
			create_log=1,
			last_execution="2019-01-01 00:00:00",
		).insert()
		self.addCleanup(delete_scheduled_job, job.name)

		failing_log_hook = {
			"doc_events": {
				"Scheduled Job Log": {
					"on_update": [
						"frappe.core.doctype.scheduled_job_type.test_scheduled_job_type.raise_import_error"
					]
				}
			}
		}

		frappe.flags.scheduled_job_ran = False
		try:
			with self.patch_hooks(failing_log_hook):
				frappe.local.doc_events_hooks = None
				job.execute()
		finally:
			frappe.local.doc_events_hooks = None

		self.assertTrue(frappe.flags.scheduled_job_ran)

		last_execution = frappe.db.get_value("Scheduled Job Type", job.name, "last_execution")
		self.assertGreater(get_datetime(last_execution), get_datetime("2019-01-01 00:00:00"))
		self.assertFalse(job.is_event_due())

	def test_cold_start(self):
		now = now_datetime()
		just_before_12_am = now.replace(hour=11, minute=59, second=30)
		just_after_12_am = now.replace(hour=0, minute=0, second=30) + timedelta(days=1)

		job = frappe.new_doc("Scheduled Job Type")
		job.frequency = "Daily"
		job.set_user_and_timestamp()

		with self.freeze_time(just_before_12_am):
			self.assertFalse(job.is_event_due())

		with self.freeze_time(just_after_12_am):
			self.assertTrue(job.is_event_due())
