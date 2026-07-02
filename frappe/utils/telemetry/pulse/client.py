from typing import Any

import frappe
from frappe.utils.caching import site_cache

from .queue import EventQueue
from .transport import PulseHTTP
from .utils import anonymize_user, pulse_host, utc_iso


@site_cache(ttl=60 * 60)
def is_enabled() -> bool:
	if not frappe.conf.get("pulse_api_key"):
		return False

	if frappe.conf.get("pulse_force_enabled"):
		return True

	return bool(not frappe.conf.get("developer_mode", 0) and frappe.get_system_settings("enable_telemetry"))


@frappe.whitelist(allow_guest=True)
def boot_config() -> dict:
	"""Direct-mode config for the browser client.

	Desk reads this from bootinfo, but frappe-ui SPAs don't have desk's
	`window.frappe.boot`, so it's also whitelisted: the telemetry plugin fetches it
	directly and app owners don't each write their own endpoint. Self-gates —
	returns ``{"enabled": False}`` when telemetry is off, so a disabled site hands
	out nothing.

	The key is a public, write-only ingest key — shipping it to the browser is by
	design. `team` is the Frappe Cloud team from the site's `fc_team` config (null
	where unset, e.g. a marketing site). `user` is the site-salted anonymized
	authenticated user, or null for a guest — the browser client then mints its own
	per-browser `anon_` id. Never the FC account.
	"""
	if not is_enabled():
		return {"enabled": False}

	# Local import: telemetry/__init__ imports this module, so a top-level import
	# would be a cycle (site_age is defined after that import runs).
	from frappe.utils.telemetry import site_age

	host = pulse_host()

	session_user = frappe.session.user
	if session_user in frappe.STANDARD_USERS:
		# null for guests/standard users: there's no server-known identity, so the
		# client falls back to its own per-browser anon id (which signup can alias).
		session_user = None

	return {
		"enabled": True,
		"host": host,
		"client_url": f"{host}/assets/pulse/js/pulse_client.js",
		"key": frappe.conf.get("pulse_api_key"),
		"site": frappe.local.site,
		"user": anonymize_user(session_user),
		"team": frappe.conf.get("fc_team"),
		"site_age": site_age(),
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
	team = team or frappe.conf.get("fc_team")

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


def identify(properties: str | dict[str, Any] | None = None):
	"""Attach attributes to the account team — upserts its Pulse profile.

	The identity subject is always this site's Frappe Cloud team (`fc_team`): a site
	belongs to exactly one team, so it's implicit and can't be mistyped — a setup
	wizard just passes properties. Server-side only (not whitelisted): posted directly
	rather than queued — it's low-frequency, and a missed call self-heals on the next
	change. Telemetry never raises to the caller.
	"""
	team = frappe.conf.get("fc_team")
	if not is_enabled() or not team:
		return

	if isinstance(properties, str):
		try:
			properties = frappe.parse_json(properties)
		except Exception as e:
			# Bad json from the caller must not break their flow — log and skip,
			# same as any other delivery failure.
			frappe.logger("pulse").error(f"pulse-client - identify: invalid properties json: {e!s}")
			return

	endpoint = frappe.conf.get("pulse_identify_endpoint") or "/api/method/pulse.api.identify"
	PulseHTTP().post(endpoint, {"team": team, "properties": properties or {}}, label="identify")


def alias(previous_id: str):
	"""Link a previous (anonymous) id to this site's account team (`fc_team`).

	The alias target is always the site's team — implicit, single-tenant. Server-side
	only (not whitelisted): identity merges must be press-controlled — a
	browser-callable alias would let anyone re-point ids and poison the graph. Same
	delivery semantics as identify.
	"""
	team = frappe.conf.get("fc_team")
	if not is_enabled() or not previous_id or not team:
		return

	endpoint = frappe.conf.get("pulse_alias_endpoint") or "/api/method/pulse.api.alias"
	PulseHTTP().post(endpoint, {"previous_id": previous_id, "team": team}, label="alias")


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
