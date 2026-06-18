from typing import Any

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils.caching import site_cache
from frappe.utils.frappecloud import on_frappecloud

from .queue import EventQueue
from .transport import PulseHTTP
from .utils import anonymize_user, utc_iso


@frappe.whitelist(allow_guest=True)
@site_cache(ttl=60 * 60)
def is_enabled() -> bool:
	return bool(
		not frappe.conf.get("developer_mode", 0)
		and frappe.conf.get("pulse_api_key")
		and on_frappecloud()
		and frappe.get_system_settings("enable_telemetry")
	)


@frappe.whitelist()
def capture(
	event_name: str,
	site: str | None = None,
	app: str | None = None,
	user: str | None = None,
	team: str | None = None,
	captured_at: str | None = None,
	properties: dict[str, Any] | None = None,
	interval: int | str | None = None,
):
	if not is_enabled():
		return

	user = user or anonymize_user(frappe.session.user)

	try:
		eq = EventQueue()
		eq.add(
			{
				"event_name": event_name,
				"captured_at": captured_at or utc_iso(),
				"app": app,
				"site": site or frappe.local.site,
				"user": user,
				"team": team,
				"properties": properties or {},
			},
			interval=interval,
		)
	except Exception as e:
		frappe.logger("pulse").error(f"pulse-client - capture failed: {e!s}")


@frappe.whitelist()
def bulk_capture(events: str | list[dict[str, Any]]):
	if not is_enabled():
		return

	if isinstance(events, str):
		events = frappe.parse_json(events)

	for event in events:
		capture(
			event.get("event_name"),
			site=event.get("site"),
			app=event.get("app"),
			user=event.get("user"),
			team=event.get("team"),
			captured_at=event.get("captured_at"),
			properties=event.get("properties"),
			interval=event.get("interval"),
		)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=1000, seconds=60 * 60)
def guest_capture(events: str | list[dict[str, Any]]):
	"""Guest-accessible capture for pre-signup surfaces (e.g. frappe.io, the FC
	signup pages) where there's no session yet — callers pass an `anon_id` as the
	event `user`.

	Split from `bulk_capture` so the authenticated desk path stays unthrottled:
	desk telemetry is high-frequency and often shares one NAT IP across many
	users, where a per-IP limit would silently drop legit events. The per-IP rate
	limit matches the framework's guest-API convention (see `www/contact.py`).
	"""
	bulk_capture(events)


def identify(user: str, properties: str | dict[str, Any] | None = None):
	"""Attach attributes to a user — upserts its Pulse Person profile.

	Server-side only (not whitelisted): press calls this in Python when a person's
	attributes change (e.g. setting an FC user's persona at signup/payment). Posted
	directly rather than queued: it's low-frequency, and a missed call self-heals on
	the next change. Telemetry never raises to the caller.
	"""
	if not is_enabled() or not user:
		return

	if isinstance(properties, str):
		properties = frappe.parse_json(properties)

	endpoint = frappe.conf.get("pulse_identify_endpoint") or "/api/method/pulse.api.identify"
	PulseHTTP().post(endpoint, {"user": user, "properties": properties or {}}, label="identify")


def alias(previous_id: str, user: str):
	"""Link a previous (anonymous) user id to a known user.

	Server-side only (not whitelisted): identity merges must be press-controlled —
	a browser-callable alias would let anyone re-point ids and poison the graph.
	Press calls this in its signup handler to stitch the pre-signup anonymous
	browser id to the FC user. Same delivery semantics as identify.
	"""
	if not is_enabled() or not previous_id or not user:
		return

	endpoint = frappe.conf.get("pulse_alias_endpoint") or "/api/method/pulse.api.alias"
	PulseHTTP().post(endpoint, {"previous_id": previous_id, "user": user}, label="alias")


def send_queued_events():
	if not is_enabled():
		return

	http = PulseHTTP()
	endpoint = frappe.conf.get("pulse_ingest_endpoint") or "/api/method/pulse.api.bulk_ingest"

	def post_batch(events):
		http.post(endpoint, {"events": events}, label="ingest", raise_on_error=True)

	EventQueue().batch_process(post_batch, batch_size=100, max_batches=10)


@frappe.whitelist()
def get_debug_info(
	fetch_events: int | str | bool | None = None, fetch_rate_limited_events: int | str | bool | None = None
):
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
