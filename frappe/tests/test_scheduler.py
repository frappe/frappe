import os
import time
from datetime import datetime, timedelta
from unittest.mock import call, patch

from rq.defaults import DEFAULT_WORKER_TTL

import frappe
from frappe.core.doctype.scheduled_job_type.scheduled_job_type import ScheduledJobType, sync_jobs
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import add_days, get_datetime
from frappe.utils import scheduler as scheduler_utils
from frappe.utils.doctor import purge_pending_jobs
from frappe.utils.scheduler import (
	DEFAULT_SCHEDULER_TICK,
	SCHEDULER_HEARTBEAT_INTERVAL,
	enqueue_events,
	is_dormant,
	is_scheduler_process_running,
	schedule_jobs_based_on_activity,
	sleep_duration,
)


def test_timeout_10():
	time.sleep(10)


def test_method():
	pass


class TestScheduler(IntegrationTestCase):
	def setUp(self):
		frappe.db.rollback()

		if not os.environ.get("CI"):
			return

		purge_pending_jobs()
		if not frappe.get_all("Scheduled Job Type", limit=1):
			sync_jobs()

	def tearDown(self):
		purge_pending_jobs()

	def test_enqueue_jobs(self):
		frappe.db.sql("update `tabScheduled Job Type` set last_execution = '2010-01-01 00:00:00'")

		enqueued_jobs = enqueue_events()

		self.assertIn("frappe.desk.notifications.clear_notifications", enqueued_jobs)
		self.assertIn("frappe.utils.change_log.check_for_update", enqueued_jobs)
		self.assertIn(
			"frappe.email.doctype.auto_email_report.auto_email_report.send_monthly",
			enqueued_jobs,
		)

	def test_queue_peeking(self):
		job = get_test_job()

		with patch.object(job, "is_job_in_queue", return_value=True):
			# 1st job is in the queue (or running), don't enqueue it again
			self.assertFalse(job.enqueue())

	@patch.object(frappe.utils.frappecloud, "on_frappecloud", return_value=True)
	@patch.dict(frappe.conf, {"developer_mode": 0})
	def test_is_dormant(self, _mock):
		last_activity = frappe.db.get_value(
			"User", filters={}, fieldname="last_active", order_by="last_active desc"
		)
		self.assertTrue(is_dormant(check_time=get_datetime("2100-01-01 00:00:00")))
		self.assertTrue(is_dormant(check_time=add_days(last_activity, 5)))
		self.assertFalse(is_dormant(check_time=last_activity))

	@patch.object(frappe.utils.frappecloud, "on_frappecloud", return_value=True)
	@patch.dict(frappe.conf, {"developer_mode": 0})
	def test_once_a_day_for_dormant(self, _mocks):
		last_activity = frappe.db.get_value(
			"User", filters={}, fieldname="last_active", order_by="last_active desc"
		)
		frappe.db.truncate("Scheduled Job Log")
		self.assertTrue(schedule_jobs_based_on_activity(check_time=get_datetime("2100-01-01 00:00:00")))
		self.assertTrue(schedule_jobs_based_on_activity(check_time=add_days(last_activity, 5)))

		# create a fake job executed 5 days from now
		job = get_test_job(method="frappe.tests.test_scheduler.test_method", frequency="Daily")
		job.execute()
		job_log = frappe.get_doc("Scheduled Job Log", dict(scheduled_job_type=job.name))
		job_log.db_set("creation", add_days(last_activity, 5), update_modified=False)
		schedule_jobs_based_on_activity.clear_cache()
		is_dormant.clear_cache()

		# inactive site with recent job, don't run
		self.assertFalse(schedule_jobs_based_on_activity(check_time=add_days(last_activity, 5)))

		# one more day has passed
		self.assertTrue(schedule_jobs_based_on_activity(check_time=add_days(last_activity, 6)))

	def test_real_time_alignment(self):
		test_cases = {
			timedelta(minutes=0): DEFAULT_SCHEDULER_TICK,
			timedelta(minutes=0, seconds=12): DEFAULT_SCHEDULER_TICK - 12,
			timedelta(minutes=1, seconds=12): DEFAULT_SCHEDULER_TICK - (1 * 60 + 12),
			timedelta(hours=23, minutes=59): 60,
			timedelta(hours=23, minutes=59, seconds=30): 30,
			timedelta(minutes=0, seconds=1): DEFAULT_SCHEDULER_TICK - 1,
			timedelta(minutes=2): DEFAULT_SCHEDULER_TICK - 2 * 60,
		}
		for delta, expected_sleep in test_cases.items():
			fake_time = datetime(2024, 1, 1) + delta
			with self.freeze_time(fake_time, is_utc=True):
				self.assertEqual(sleep_duration(DEFAULT_SCHEDULER_TICK), expected_sleep, delta)


class TestSchedulerHeartbeat(UnitTestCase):
	@patch("frappe.utils.scheduler.FileLock")
	@patch("frappe.utils.scheduler.set_niceness")
	@patch("frappe.utils.scheduler.get_scheduler_tick", return_value=240)
	@patch("frappe.utils.scheduler.sleep_duration", return_value=120)
	@patch("frappe.utils.scheduler._sleep_with_scheduler_heartbeat")
	@patch("frappe.utils.scheduler.enqueue_events_for_all_sites", side_effect=RuntimeError("stop"))
	def test_start_scheduler_uses_heartbeat_sleep(
		self, enqueue_events, heartbeat_sleep, _sleep_duration, _get_tick, _set_niceness, file_lock
	):
		with self.assertRaisesRegex(RuntimeError, "stop"):
			scheduler_utils.start_scheduler()

		file_lock.return_value.acquire.assert_called_once_with(blocking=False)
		heartbeat_sleep.assert_called_once_with(120)
		enqueue_events.assert_called_once_with()

	@patch("frappe.utils.scheduler.enqueue_events_for_site")
	@patch("frappe.utils.scheduler._update_scheduler_heartbeat")
	@patch("frappe.utils.scheduler.random.shuffle")
	@patch("frappe.utils.scheduler.get_sites", return_value=["site-1", "site-2"])
	@patch("frappe.utils.scheduler.frappe.init_site")
	def test_scheduler_heartbeat_before_each_site(
		self, _init_site, _get_sites, _shuffle, update_heartbeat, enqueue_events_for_site
	):
		scheduler_utils.enqueue_events_for_all_sites()

		self.assertEqual(update_heartbeat.call_count, 2)
		self.assertEqual(
			enqueue_events_for_site.call_args_list,
			[call(site="site-1"), call(site="site-2")],
		)

	@patch("frappe.utils.scheduler.get_bench_id", return_value="test-bench")
	@patch("frappe.utils.scheduler.get_redis_conn")
	def test_scheduler_heartbeat(self, get_redis_conn, _get_bench_id):
		redis = get_redis_conn.return_value

		with patch("frappe.utils.scheduler.time.time", return_value=123):
			scheduler_utils._update_scheduler_heartbeat()

		redis.set.assert_called_once_with(
			"test-bench:scheduler:heartbeat",
			123,
			ex=DEFAULT_WORKER_TTL,
		)

		redis.exists.return_value = 1
		self.assertTrue(is_scheduler_process_running())

		redis.exists.return_value = 0
		self.assertFalse(is_scheduler_process_running())

	@patch("frappe.utils.scheduler.frappe.logger")
	@patch("frappe.utils.scheduler.get_redis_conn")
	def test_scheduler_heartbeat_redis_failure(self, get_redis_conn, logger):
		redis = get_redis_conn.return_value
		redis.set.side_effect = scheduler_utils.RedisError("unavailable")

		scheduler_utils._update_scheduler_heartbeat()

		logger.return_value.warning.assert_called_once_with(
			"Failed to update scheduler heartbeat",
			exc_info=True,
		)

	@patch("frappe.utils.scheduler._update_scheduler_heartbeat")
	@patch("frappe.utils.scheduler.time.sleep")
	@patch("frappe.utils.scheduler.time.monotonic", side_effect=(0, 0, 30, 60))
	def test_scheduler_heartbeat_during_sleep(self, _monotonic, sleep, update_heartbeat):
		scheduler_utils._sleep_with_scheduler_heartbeat(60)

		self.assertEqual(update_heartbeat.call_count, 3)
		self.assertEqual(
			sleep.call_args_list,
			[
				call(SCHEDULER_HEARTBEAT_INTERVAL),
				call(SCHEDULER_HEARTBEAT_INTERVAL),
			],
		)


def get_test_job(method="frappe.tests.test_scheduler.test_timeout_10", frequency="All") -> ScheduledJobType:
	if not frappe.db.exists("Scheduled Job Type", dict(method=method)):
		job = frappe.get_doc(
			doctype="Scheduled Job Type",
			method=method,
			last_execution="2010-01-01 00:00:00",
			frequency=frequency,
		).insert()
	else:
		job = frappe.get_doc("Scheduled Job Type", dict(method=method))
		job.db_set("last_execution", "2010-01-01 00:00:00")
		job.db_set("frequency", frequency)
	frappe.db.commit()

	return job
