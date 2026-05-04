import time
from contextlib import suppress
from json import JSONDecodeError

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import get_request_session
from frappe.utils.caching import site_cache
from frappe.utils.frappecloud import on_frappecloud

from .utils import anonymize_user, ensure_http, parse_interval, utc_iso


@frappe.whitelist()
@site_cache(ttl=60 * 60)
def is_enabled() -> bool:
	return bool(
		not frappe.conf.get("developer_mode", 0)
		and frappe.conf.get("pulse_api_key")
		and on_frappecloud()
		and frappe.get_system_settings("enable_telemetry")
	)


@frappe.whitelist()
def capture(event_name, site=None, app=None, user=None, captured_at=None, properties=None, interval=None):
	if not is_enabled():
		return

	try:
		eq = EventQueue()
		eq.add(
			{
				"event_name": event_name,
				"captured_at": captured_at or utc_iso(),
				"app": app,
				"user": anonymize_user(user),
				"site": site or frappe.local.site,
				"properties": properties,
			},
			interval=interval,
		)
	except Exception as e:
		frappe.logger("pulse").error(f"pulse-client - capture failed: {e!s}")


@frappe.whitelist()
def bulk_capture(events):
	if not is_enabled():
		return

	if isinstance(events, str):
		events = frappe.parse_json(events)

	for event in events:
		capture(
			event.get("event_name"),
			site=event.get("site"),
			app=event.get("app"),
			user=event.get("user") or frappe.session.user,
			captured_at=event.get("captured_at"),
			properties=event.get("properties"),
			interval=event.get("interval"),
		)


def send_queued_events():
	if not is_enabled():
		return

	eq = EventQueue()
	eq.batch_process(post, batch_size=100, max_batches=10)


def post(events):
	session = _create_session()
	url = _get_ingest_url()
	data = frappe.as_json({"events": events})
	resp = session.post(url, data=data, timeout=15)
	if not (200 <= resp.status_code < 300):
		msg = f"pulse-client - post failed: {resp.status_code} {resp.text}"
		frappe.logger("pulse").error(msg)
		raise Exception(msg)
	return resp


def _create_session():
	api_key = frappe.conf.get("pulse_api_key")
	session = get_request_session()
	session.headers.update(
		{
			"Content-Type": "application/json",
			"X-Pulse-API-Key": api_key,
		}
	)
	return session


def _get_ingest_url():
	host = frappe.conf.get("pulse_host") or "https://pulse.m.frappe.cloud"
	host = ensure_http(host)
	host = host.rstrip("/")

	endpoint = frappe.conf.get("pulse_ingest_endpoint") or "/api/method/pulse.api.bulk_ingest"
	endpoint = endpoint.lstrip("/")

	return f"{host}/{endpoint}"


class EventQueue:
	def __init__(self):
		self.queue = "pulse-client:events"
		self.queue_size = 10000
		self.ratelimit_prefix = "pulse-client:last_sent:"

	@property
	def length(self):
		return frappe.cache.llen(self.queue)

	def add(self, event, interval=None):
		if self._is_ratelimited(event, interval):
			return

		self._queue_event(event)
		self._update_ratelimit(event, interval)

	def _is_ratelimited(self, event, interval):
		if not interval:
			return False

		interval_seconds = parse_interval(interval)
		event_key = self._get_event_key(event)
		last_sent_key = f"{self.ratelimit_prefix}{event_key}"
		last_sent = frappe.cache.get_value(last_sent_key)

		if last_sent and time.monotonic() - float(last_sent) < interval_seconds:
			return True

		return False

	def _get_event_key(self, event):
		return f"{event.get('event_name')}:{event.get('site')}:{event.get('app')}:{event.get('user')}"

	def _update_ratelimit(self, event, interval):
		if not interval:
			return
		event_key = self._get_event_key(event)
		last_sent_key = f"{self.ratelimit_prefix}{event_key}"
		frappe.cache.set_value(last_sent_key, time.monotonic())

	def _queue_event(self, event):
		frappe.cache.lpush(self.queue, frappe.as_json(event))
		frappe.cache.ltrim(self.queue, 0, self.queue_size - 1)

	def batch_process(self, fn, batch_size=100, max_batches=10, max_retries=3, backoff_seconds=1):
		pending_events = None
		retry_attempts = 0

		for _ in range(max_batches):
			events = pending_events or self.collect(batch_size)
			if not events:
				break

			try:
				fn(events)
				pending_events = None
				retry_attempts = 0
			except Exception as e:
				retry_attempts += 1
				if retry_attempts > max_retries:
					# Tried enough times, re-queue pending events and exit.
					frappe.logger("pulse").error(f"pulse-client - max retries reached: {e!s}")
					self._requeue_events(events)
					break

				pending_events = events
				time.sleep(backoff_seconds * (2 ** (retry_attempts - 1)))
				frappe.logger("pulse").error(f"pulse-client - retrying batch due to error: {e!s}")

	def collect(self, batch_size=100):
		events = []
		for _ in range(batch_size):
			event_json = frappe.cache.rpop(self.queue)
			if not event_json:
				break
			data = self._decode_event(event_json)
			if data:
				events.append(data)
		return events

	def _requeue_events(self, events):
		# Preserve original processing order (FIFO): we pop from right, so re-add in reverse.
		for event in reversed(events):
			frappe.cache.rpush(self.queue, frappe.as_json(event))
		frappe.cache.ltrim(self.queue, 0, self.queue_size - 1)

	def _decode_event(self, event_json):
		event_json = event_json.decode()
		with suppress(JSONDecodeError):
			return frappe.parse_json(event_json)

	def get_events(self, limit=20):
		events = []
		for _ in range(limit):
			event_json = frappe.cache.lindex(self.queue, _)
			if not event_json:
				break
			data = self._decode_event(event_json)
			if data:
				events.append(data)
		return events

	def get_last_sent_events(self, limit=20):
		events = []
		keys = frappe.cache.get_keys(f"{self.ratelimit_prefix}*")[:limit]
		for key in keys:
			last_sent = frappe.cache.get_value(key)
			event_key = key.replace(self.ratelimit_prefix, "")
			events.append(
				{
					"event_key": event_key,
					"last_sent": last_sent,
				}
			)
		return events


@frappe.whitelist()
def get_debug_info(fetch_events=None, fetch_rate_limited_events=None):
	frappe.only_for("System Manager")

	info = frappe._dict()
	info.is_enabled = is_enabled()

	if info.is_enabled:
		eq = EventQueue()
		info.queued_event_count = eq.length

		if fetch_events:
			limit = int(fetch_events) if str(fetch_events).isdigit() else 20
			info.queued_events = eq.get_events(limit)

		if fetch_rate_limited_events:
			limit = int(fetch_rate_limited_events) if str(fetch_rate_limited_events).isdigit() else 20
			info.rate_limited_events = eq.get_last_sent_events(limit)

	return info
