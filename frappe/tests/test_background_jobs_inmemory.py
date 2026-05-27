from unittest.mock import MagicMock, patch

from redis.exceptions import ConnectionError

import frappe
from frappe.tests.classes.integration_test_case import IntegrationTestCase
from frappe.utils.background_jobs import enqueue


class TestBackgroundJobsInMemory(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.original_in_migrate = frappe.local.flags.in_migrate
		frappe.local.flags.in_migrate = False
		frappe.db.after_commit.clear()

	def tearDown(self):
		frappe.local.flags.in_migrate = self.original_in_migrate
		frappe.db.after_commit.clear()
		super().tearDown()

	def mock_job_method(self):
		pass

	@patch("frappe.utils.background_jobs.get_queue")
	@patch("frappe.utils.background_jobs.execute_job")
	@patch("frappe.utils.background_jobs._in_memory_pool")
	def test_in_memory_async_submission(self, mock_pool, mock_execute_job, mock_get_queue):
		# Simulate Redis offline
		mock_get_queue.side_effect = ConnectionError("Redis is down")

		from frappe.utils.redis_wrapper import MemoryCacheWrapper

		with patch("frappe.cache", new=MemoryCacheWrapper()):
			enqueue(self.mock_job_method, queue="default", is_async=True, enqueue_after_commit=False)

			# Check that ThreadPool was submitted to
			mock_pool.submit.assert_called_once()

			# Check args passed to submit
			args, kwargs = mock_pool.submit.call_args
			self.assertEqual(args[0], mock_execute_job)  # The wrapped execute_job
			self.assertEqual(kwargs.get("is_async"), True)

	@patch("frappe.utils.background_jobs.get_queue")
	@patch("frappe.call")
	@patch("frappe.utils.background_jobs._in_memory_pool")
	def test_in_memory_sync_during_migration(self, mock_pool, mock_frappe_call, mock_get_queue):
		# Simulate Redis offline
		mock_get_queue.side_effect = ConnectionError("Redis is down")

		# Flag system as migrating
		frappe.local.flags.in_migrate = True

		from frappe.utils.redis_wrapper import MemoryCacheWrapper

		with patch("frappe.cache", new=MemoryCacheWrapper()):
			enqueue(self.mock_job_method, queue="default", is_async=True, enqueue_after_commit=False)

			# Should bypass thread pool and run inline
			mock_pool.submit.assert_not_called()
			mock_frappe_call.assert_called_once()

	@patch("frappe.utils.background_jobs.get_queue")
	@patch("frappe.utils.background_jobs._in_memory_pool")
	def test_enqueue_after_commit_deferred(self, mock_pool, mock_get_queue):
		# Simulate Redis offline
		mock_get_queue.side_effect = ConnectionError("Redis is down")

		from frappe.utils.redis_wrapper import MemoryCacheWrapper

		with patch("frappe.cache", new=MemoryCacheWrapper()):
			enqueue(self.mock_job_method, queue="default", is_async=True, enqueue_after_commit=True)

			# Should NOT be submitted immediately
			mock_pool.submit.assert_not_called()

			# Should be appended to after_commit hook
			self.assertEqual(len(frappe.db.after_commit), 1)

			# Simulate commit which fires hooks
			frappe.db.commit()

			# NOW it should be submitted
			mock_pool.submit.assert_called_once()

	@patch("frappe.utils.background_jobs.get_queue")
	@patch("frappe.utils.background_jobs._in_memory_pool")
	def test_redis_available_standard_flow(self, mock_pool, mock_get_queue):
		# Mock a valid RQ Queue
		mock_q = MagicMock()
		mock_get_queue.return_value = mock_q

		with patch("frappe.utils.background_jobs._check_queue_size"):
			enqueue(self.mock_job_method, queue="default", is_async=True, enqueue_after_commit=False)

			# ThreadPool bypassed completely
			mock_pool.submit.assert_not_called()

			# RQ queue enqueue_call triggered
			mock_q.enqueue_call.assert_called_once()
