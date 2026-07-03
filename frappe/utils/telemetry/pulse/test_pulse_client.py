import time
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.telemetry.pulse.client import (
	EventQueue,
	alias,
	boot_config,
	capture,
	identify,
	is_enabled,
)
from frappe.utils.telemetry.pulse.utils import anonymize_user, parse_interval


class TestPulseClient(IntegrationTestCase):
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

	def test_requeue_survives_a_full_queue(self):
		"""A failed batch requeued onto a full queue must not be trimmed away:
		overflow should shed the newest captures, not the events being retried."""
		eq = EventQueue()
		queue_size = eq.queue_size

		def make(name):
			return {
				"event_name": name,
				"captured_at": "2026-01-01T00:00:00",
				"app": "frappe",
				"user": "test@example.com",
				"site": "test.localhost",
				"properties": {},
			}

		# Ingest is down: this batch was collected and exhausted its retries.
		failed = [make(f"failed_{i}") for i in range(5)]
		# Meanwhile fresh captures refilled the queue to capacity.
		for i in range(queue_size):
			eq.add(make(f"fresh_{i}"))
		self.assertEqual(eq.length, queue_size)

		eq._requeue_events(failed)

		# Still bounded, and the failed batch sits at the consume end intact.
		self.assertEqual(eq.length, queue_size)
		drained = eq.collect(batch_size=len(failed))
		self.assertEqual([e["event_name"] for e in drained], [e["event_name"] for e in failed])


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


class TestTelemetryGate(TestPulseClient):
	"""is_enabled() is the privacy gate; boot_config() is the public endpoint that
	must stay shut when the gate is off. Exercised together through real config."""

	def _conf(self, **overrides):
		conf = {"pulse_api_key": "k", "developer_mode": 0, "pulse_force_enabled": 0}
		conf.update(overrides)
		is_enabled.clear_cache()
		self.addCleanup(is_enabled.clear_cache)
		return patch.dict(frappe.conf, conf)

	def test_off_by_default_and_endpoint_leaks_nothing(self):
		with self._conf(pulse_api_key=None), patch("frappe.get_system_settings", return_value=True):
			self.assertFalse(is_enabled())
			self.assertEqual(boot_config(), {"enabled": False})  # public endpoint stays shut

	def test_enabled_when_configured(self):
		with (
			self._conf(pulse_host="https://pulse.example.com"),
			patch("frappe.get_system_settings", return_value=True),
		):
			self.assertTrue(is_enabled())
			cfg = boot_config()

		self.assertEqual(cfg["key"], "k")
		self.assertEqual(cfg["client_url"], "https://pulse.example.com/assets/pulse/js/pulse_client.js")
		self.assertIsNone(cfg["team"])

	def test_force_enabled_overrides(self):
		# Escape hatch: on despite dev mode / telemetry off, but still requires an ingest key.
		with (
			self._conf(pulse_force_enabled=1, pulse_api_key="k", developer_mode=1),
			patch("frappe.get_system_settings", return_value=False),
		):
			self.assertTrue(is_enabled())

	def test_boot_config_user_identity(self):
		with self._conf(), patch("frappe.get_system_settings", return_value=True):
			# Guests have no server-known identity → null; the client mints its own anon id.
			with patch.dict(frappe.session, {"user": "Guest"}):
				self.assertIsNone(boot_config()["user"])
			# Known users → the site-salted anonymized id.
			with patch.dict(frappe.session, {"user": "priya@example.com"}):
				self.assertEqual(boot_config()["user"], anonymize_user("priya@example.com"))

	def test_boot_config_team_from_site_config(self):
		# The site's fc_team is handed to the browser, so its events carry the team.
		with self._conf(fc_team="team_x"), patch("frappe.get_system_settings", return_value=True):
			self.assertEqual(boot_config()["team"], "team_x")

	def test_boot_config_includes_site_age(self):
		# Exposed so frappe-ui apps can gate onboarding-only tracking the way desk does.
		with (
			self._conf(),
			patch("frappe.get_system_settings", return_value=True),
			patch("frappe.utils.telemetry.site_age", return_value=3),
		):
			self.assertEqual(boot_config()["site_age"], 3)

	def test_client_url_is_absolute_when_host_lacks_scheme(self):
		# A scheme-less pulse_host must still yield an absolute client_url, else the
		# browser resolves the import against the Frappe origin and telemetry never loads.
		with (
			self._conf(pulse_host="pulse.example.com"),
			patch("frappe.get_system_settings", return_value=True),
		):
			cfg = boot_config()

		self.assertEqual(cfg["host"], "https://pulse.example.com")
		self.assertEqual(cfg["client_url"], "https://pulse.example.com/assets/pulse/js/pulse_client.js")


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
			user="fc_priya",
			team="team_test",
			properties={"key": "value"},
		)

		self.assertEqual(eq.length, 1)
		events = eq.collect(batch_size=1)
		self.assertEqual(events[0]["event_name"], "test_event")
		self.assertEqual(events[0]["properties"]["key"], "value")

	@patch("frappe.utils.telemetry.pulse.client.is_enabled")
	def test_capture_user_and_team_group(self, mock_enabled):
		"""On events, team is the identity subject and user is a per-actor dimension"""
		is_enabled.clear_cache()
		mock_enabled.return_value = True
		eq = EventQueue()

		capture("test_event", site="test.localhost", user="fc_priya", team="team_priya")

		events = eq.collect(batch_size=1)
		# user is always anonymized (the privacy gate); team is the raw group id
		self.assertEqual(events[0]["user"], anonymize_user("fc_priya"))
		self.assertEqual(events[0]["team"], "team_priya")

	@patch("frappe.utils.telemetry.pulse.client.is_enabled")
	def test_capture_defaults_user_and_leaves_team_empty(self, mock_enabled):
		"""user defaults to the anon site user; team is null when the site has no
		fc_team configured (e.g. a marketing site)"""
		is_enabled.clear_cache()
		mock_enabled.return_value = True
		eq = EventQueue()

		capture("test_event", site="test.localhost")

		events = eq.collect(batch_size=1)
		# user defaults to the (anonymized) session user
		self.assertEqual(events[0]["user"], anonymize_user(frappe.session.user))
		# no fc_team in conf → team stays null
		self.assertIsNone(events[0]["team"])

	@patch("frappe.utils.telemetry.pulse.client.is_enabled")
	def test_capture_defaults_team_from_site_config(self, mock_enabled):
		"""A site with fc_team set stamps it on events without the caller passing it."""
		is_enabled.clear_cache()
		mock_enabled.return_value = True
		eq = EventQueue()

		with patch.dict(frappe.conf, {"fc_team": "team_x"}):
			capture("test_event", site="test.localhost")

		events = eq.collect(batch_size=1)
		self.assertEqual(events[0]["team"], "team_x")


class TestIdentify(TestPulseClient):
	@patch("frappe.utils.telemetry.pulse.transport.PulseHTTP._session")
	@patch("frappe.utils.telemetry.pulse.client.is_enabled")
	def test_identify_noop_when_disabled(self, mock_enabled, mock_session):
		"""identify does nothing (and posts nothing) when telemetry is disabled"""
		is_enabled.clear_cache()
		mock_enabled.return_value = False

		identify({"plan": "pro"})

		mock_session.assert_not_called()

	@patch("frappe.utils.telemetry.pulse.transport.PulseHTTP._session")
	@patch("frappe.utils.telemetry.pulse.client.is_enabled")
	def test_identify_swallows_bad_json(self, mock_enabled, mock_session):
		"""A malformed properties string is logged, not raised — and nothing is posted."""
		is_enabled.clear_cache()
		mock_enabled.return_value = True

		with patch.dict(frappe.conf, {"fc_team": "team_test"}):
			identify("{not valid json")  # must not raise

		mock_session.assert_not_called()

	@patch("frappe.utils.telemetry.pulse.transport.PulseHTTP._session")
	@patch("frappe.utils.telemetry.pulse.client.is_enabled")
	def test_identify_posts_profile(self, mock_enabled, mock_session):
		"""identify posts the team + properties to the identify endpoint"""
		is_enabled.clear_cache()
		mock_enabled.return_value = True

		posted = {}

		class _Resp:
			status_code = 200

		def _fake_post(url, data=None, timeout=None):
			posted["url"] = url
			posted["data"] = frappe.parse_json(data)
			return _Resp()

		mock_session.return_value = type("_Session", (), {"post": staticmethod(_fake_post)})()

		with patch.dict(frappe.conf, {"fc_team": "team_x"}):
			identify({"persona": "founder"})

		self.assertEqual(posted["data"]["team"], "team_x")
		self.assertEqual(posted["data"]["properties"]["persona"], "founder")
		self.assertTrue(posted["url"].endswith("/api/method/pulse.api.identify"))

	@patch("frappe.utils.telemetry.pulse.transport.PulseHTTP._session")
	@patch("frappe.utils.telemetry.pulse.client.is_enabled")
	def test_alias_posts_mapping(self, mock_enabled, mock_session):
		"""alias posts the previous_id → team mapping to the alias endpoint"""
		is_enabled.clear_cache()
		mock_enabled.return_value = True

		posted = {}

		class _Resp:
			status_code = 200

		def _fake_post(url, data=None, timeout=None):
			posted["url"] = url
			posted["data"] = frappe.parse_json(data)
			return _Resp()

		mock_session.return_value = type("_Session", (), {"post": staticmethod(_fake_post)})()

		with patch.dict(frappe.conf, {"fc_team": "team_x"}):
			alias("anon_8f2c")

		self.assertEqual(posted["data"]["previous_id"], "anon_8f2c")
		self.assertEqual(posted["data"]["team"], "team_x")
		self.assertTrue(posted["url"].endswith("/api/method/pulse.api.alias"))


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
		self.assertTrue(anon_user.startswith("user_"))
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
