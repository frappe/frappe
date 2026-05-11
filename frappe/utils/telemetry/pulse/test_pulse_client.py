import time
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.telemetry.pulse.client import EventQueue, capture, is_enabled
from frappe.utils.telemetry.pulse.utils import anonymize_user, parse_interval


class TestPulseClient(FrappeTestCase):
	def setUp(self):
		super().setUp()
		# Clear any existing events from queue
		eq = EventQueue()
		while eq.length > 0:
			eq.collect(batch_size=1000)
		frappe.cache.delete_keys("pulse-client:")

	def tearDown(self):
		# Clean up after tests
		eq = EventQueue()
		while eq.length > 0:
			eq.collect(batch_size=1000)
		frappe.cache.delete_keys("pulse-client:")
		super().tearDown()


class TestEventQueue(TestPulseClient):
	def test_queue_operations(self):
		"""Test queue add, collect, and FIFO behavior"""
		eq = EventQueue()

		# Add events
		for i in range(10):
			event = {
				"event_name": f"test_event_{i}",
				"captured_at": "2026-01-01T00:00:00",
				"app": "frappe",
				"user": "test@example.com",
				"site": "test.localhost",
				"properties": {},
			}
			eq.add(event)

		self.assertEqual(eq.length, 10)

		# Collect events (FIFO order)
		events = eq.collect(batch_size=5)
		self.assertEqual(len(events), 5)
		self.assertEqual(eq.length, 5)
		self.assertEqual(events[0]["event_name"], "test_event_0")

	def test_queue_size_limit(self):
		"""Test that queue respects size limit"""
		eq = EventQueue()
		queue_size = eq.queue_size

		# Add more events than the queue size
		for i in range(queue_size + 100):
			event = {
				"event_name": f"test_event_{i}",
				"captured_at": "2026-01-01T00:00:00",
				"app": "frappe",
				"user": "test@example.com",
				"site": "test.localhost",
				"properties": {},
			}
			eq.add(event)

		# Queue should not exceed max size
		self.assertEqual(eq.length, queue_size)

	def test_requeue_events(self):
		"""Test requeueing events preserves order"""
		eq = EventQueue()

		# Add events
		event_names = ["event_1", "event_2", "event_3"]
		for name in event_names:
			event = {
				"event_name": name,
				"captured_at": "2026-01-01T00:00:00",
				"app": "frappe",
				"user": "test@example.com",
				"site": "test.localhost",
				"properties": {},
			}
			eq.add(event)

		# Collect and requeue
		events = eq.collect(batch_size=3)
		eq._requeue_events(events)

		# Check order is preserved
		requeued = eq.collect(batch_size=3)
		for i, event in enumerate(requeued):
			self.assertEqual(event["event_name"], event_names[i])


class TestRateLimiting(TestPulseClient):
	def test_ratelimit_basic(self):
		"""Test basic rate limiting functionality"""
		eq = EventQueue()

		event = {
			"event_name": "test_event",
			"captured_at": "2026-01-01T00:00:00",
			"app": "frappe",
			"user": "test@example.com",
			"site": "test.localhost",
			"properties": {},
		}

		# First event should be added
		eq.add(event, interval="5s")
		self.assertEqual(eq.length, 1)

		# Second event should be rate-limited
		eq.add(event, interval="5s")
		self.assertEqual(eq.length, 1)

	def test_ratelimit_different_events(self):
		"""Test that rate limiting is per-event"""
		eq = EventQueue()

		event1 = {
			"event_name": "event_1",
			"captured_at": "2026-01-01T00:00:00",
			"app": "frappe",
			"user": "test@example.com",
			"site": "test.localhost",
			"properties": {},
		}

		event2 = {
			"event_name": "event_2",
			"captured_at": "2026-01-01T00:00:00",
			"app": "frappe",
			"user": "test@example.com",
			"site": "test.localhost",
			"properties": {},
		}

		# Both events should be added as they are different
		eq.add(event1, interval="5s")
		eq.add(event2, interval="5s")
		self.assertEqual(eq.length, 2)

	def test_ratelimit_expiry(self):
		"""Test that rate limit expires after interval"""
		eq = EventQueue()

		event = {
			"event_name": "test_event",
			"captured_at": "2026-01-01T00:00:00",
			"app": "frappe",
			"user": "test@example.com",
			"site": "test.localhost",
			"properties": {},
		}

		# Add event with short interval
		eq.add(event, interval="1s")
		self.assertEqual(eq.length, 1)

		# Wait for interval to expire
		time.sleep(1.1)

		# Event should be added again
		eq.add(event, interval="1s")
		self.assertEqual(eq.length, 2)


class TestBatchProcessing(TestPulseClient):
	def test_batch_process_success(self):
		"""Test successful batch processing"""
		eq = EventQueue()
		processed = []

		def process_fn(events):
			processed.extend(events)

		# Add events
		for i in range(15):
			event = {
				"event_name": f"test_event_{i}",
				"captured_at": "2026-01-01T00:00:00",
				"app": "frappe",
				"user": "test@example.com",
				"site": "test.localhost",
				"properties": {},
			}
			eq.add(event)

		# Process in batches
		eq.batch_process(process_fn, batch_size=10, max_batches=2)

		# All events should be processed
		self.assertEqual(len(processed), 15)
		self.assertEqual(eq.length, 0)

	def test_batch_process_with_failure_and_retry(self):
		"""Test batch processing with failure and retry"""
		eq = EventQueue()
		call_count = 0

		def failing_fn(events):
			nonlocal call_count
			call_count += 1
			if call_count < 3:
				raise Exception("Temporary failure")
			return True

		# Add events
		for i in range(5):
			event = {
				"event_name": f"test_event_{i}",
				"captured_at": "2026-01-01T00:00:00",
				"app": "frappe",
				"user": "test@example.com",
				"site": "test.localhost",
				"properties": {},
			}
			eq.add(event)

		# Process with retries
		eq.batch_process(failing_fn, batch_size=10, max_retries=5, backoff_seconds=0.1)

		# Should succeed after retries
		self.assertGreaterEqual(call_count, 3)
		self.assertEqual(eq.length, 0)

	def test_batch_process_max_retries_exceeded(self):
		"""Test batch processing when max retries is exceeded"""
		eq = EventQueue()

		def always_failing_fn(events):
			raise Exception("Always fails")

		# Add events
		for i in range(5):
			event = {
				"event_name": f"test_event_{i}",
				"captured_at": "2026-01-01T00:00:00",
				"app": "frappe",
				"user": "test@example.com",
				"site": "test.localhost",
				"properties": {},
			}
			eq.add(event)

		# Process with limited retries
		eq.batch_process(always_failing_fn, batch_size=10, max_retries=2, backoff_seconds=0.1)

		# Events should be requeued
		self.assertEqual(eq.length, 5)


class TestCapture(TestPulseClient):
	@patch("frappe.utils.telemetry.pulse.client.is_enabled")
	def test_capture_when_disabled(self, mock_enabled):
		"""Test that capture does nothing when disabled"""
		is_enabled.clear_cache()
		mock_enabled.return_value = False
		eq = EventQueue()

		capture("test_event", site="test.localhost")

		self.assertEqual(eq.length, 0)

	@patch("frappe.utils.telemetry.pulse.client.is_enabled")
	def test_capture_basic(self, mock_enabled):
		"""Test basic event capture"""
		is_enabled.clear_cache()
		mock_enabled.return_value = True
		eq = EventQueue()

		capture(
			"test_event",
			site="test.localhost",
			app="frappe",
			user="test@example.com",
			properties={"key": "value"},
		)

		self.assertEqual(eq.length, 1)
		events = eq.collect(batch_size=1)
		self.assertEqual(events[0]["event_name"], "test_event")
		self.assertEqual(events[0]["properties"]["key"], "value")

	@patch("frappe.utils.telemetry.pulse.client.is_enabled")
	def test_capture_anonymizes_user(self, mock_enabled):
		"""Test that user is anonymized"""
		is_enabled.clear_cache()
		mock_enabled.return_value = True
		eq = EventQueue()

		test_user = "test@example.com"
		capture("test_event", site="test.localhost", user=test_user)

		events = eq.collect(batch_size=1)
		# User should be anonymized
		self.assertNotEqual(events[0]["user"], test_user)
		self.assertTrue(events[0]["user"].startswith("anon_"))


class TestUtils(TestPulseClient):
	def test_parse_interval(self):
		"""Test parsing various interval formats"""
		# Seconds
		self.assertEqual(parse_interval(60), 60)
		self.assertEqual(parse_interval("60"), 60)

		# Minutes, hours, days, weeks
		self.assertEqual(parse_interval("1m"), 60)
		self.assertEqual(parse_interval("1h"), 3600)
		self.assertEqual(parse_interval("1d"), 86400)
		self.assertEqual(parse_interval("1w"), 604800)

		# Invalid formats
		with self.assertRaises(ValueError):
			parse_interval("1x")

	def test_anonymize_user(self):
		"""Test user anonymization"""
		user = "test@example.com"
		anon_user = anonymize_user(user)

		# Should be anonymized and consistent
		self.assertNotEqual(anon_user, user)
		self.assertTrue(anon_user.startswith("anon_"))
		self.assertEqual(anonymize_user(user), anon_user)

		# Standard users not anonymized
		for standard_user in frappe.STANDARD_USERS:
			self.assertEqual(anonymize_user(standard_user), standard_user)


class TestEventQueueDecoding(TestPulseClient):
	def test_decode_valid_event(self):
		"""Test decoding valid event JSON"""
		eq = EventQueue()

		event = {
			"event_name": "test_event",
			"captured_at": "2026-01-01T00:00:00",
			"app": "frappe",
			"user": "test@example.com",
			"site": "test.localhost",
			"properties": {},
		}

		# Add and retrieve
		eq.add(event)
		event_json = frappe.cache.rpop(eq.queue)

		decoded = eq._decode_event(event_json)
		self.assertIsNotNone(decoded)
		self.assertEqual(decoded["event_name"], "test_event")

	def test_decode_invalid_json(self):
		"""Test decoding invalid JSON"""
		eq = EventQueue()

		# Invalid JSON should return None
		decoded = eq._decode_event(b"invalid json{")
		self.assertIsNone(decoded)


class TestEventKey(TestPulseClient):
	def test_event_key_generation_and_uniqueness(self):
		"""Test event key generation and uniqueness for rate limiting"""
		eq = EventQueue()

		event1 = {
			"event_name": "event_1",
			"app": "frappe",
			"user": "user1@example.com",
			"site": "test.localhost",
		}

		event2 = {
			"event_name": "event_2",
			"app": "frappe",
			"user": "user1@example.com",
			"site": "test.localhost",
		}

		# Test key composition
		key1 = eq._get_event_key(event1)
		self.assertIn("event_1", key1)
		self.assertIn("test.localhost", key1)
		self.assertIn("frappe", key1)

		# Test uniqueness
		key2 = eq._get_event_key(event2)
		self.assertNotEqual(key1, key2)
