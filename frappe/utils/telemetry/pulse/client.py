from typing import Any

import frappe
from frappe.utils.caching import site_cache

from .queue import EventQueue
from .transport import PulseHTTP
from .utils import anonymize_user, pulse_host, utc_iso


@site_cache(ttl=60 * 60)
def is_enabled() -> bool:
	if frappe.conf.get("pulse_force_enabled"):
		return True

	return bool(
		not frappe.conf.get("developer_mode", 0)
		and frappe.conf.get("pulse_api_key")
		and frappe.get_system_settings("enable_telemetry")
	)


@frappe.whitelist(allow_guest=True)
def boot_config() -> dict:
	"""Direct-mode config for the browser client.

	Desk reads this from bootinfo, but frappe-ui SPAs don't have desk's
	`window.frappe.boot`, so it's also whitelisted: the telemetry plugin fetches it
	directly and app owners don't each write their own endpoint. Self-gates —
	returns ``{"enabled": False}`` when telemetry is off, so a disabled site hands
	out nothing.

	The key is a public, write-only ingest key — shipping it to the browser is by
	design. On a product site `team` is null (it's joined from `site` downstream);
	`user` is the site-salted anonymous id, never the FC account.
	"""
	if not is_enabled():
		return {"enabled": False}

	host = pulse_host()
	return {
		"enabled": True,
		"host": host,
		"client_url": f"{host}/assets/pulse/js/pulse_client.js",
		"key": frappe.conf.get("pulse_api_key"),
		"site": frappe.local.site,
		"user": anonymize_user(frappe.session.user),
		"team": None,
	}


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

	user = user or frappe.session.user

	try:
		eq = EventQueue()
		eq.add(
			{
				"event_name": event_name,
				"captured_at": captured_at or utc_iso(),
				"app": app,
				"site": site or frappe.local.site,
				"user": anonymize_user(user),
				"team": team,
				"properties": properties or {},
			},
			interval=interval,
		)
	except Exception as e:
		frappe.logger("pulse").error(f"pulse-client - capture failed: {e!s}")


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
