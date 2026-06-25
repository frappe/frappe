import time
from contextlib import suppress

from orjson import JSONDecodeError

import frappe

from .utils import parse_interval


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
		return f"{event.get('event_name')}:{event.get('user')}:{event.get('team')}:{event.get('site')}:{event.get('app')}"

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
		# Keep the rightmost (consume-end) queue_size: the requeued batch sits there and
		# must survive. Trimming to the left here would drop it; instead overflow sheds
		# the newest captures from the left, matching the producer's keep-newest bound.
		frappe.cache.ltrim(self.queue, -self.queue_size, -1)

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
