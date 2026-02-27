"""Basic telemetry for improving apps.

WARNING: Everything in this file should be treated "internal" and is subjected to change or get
removed without any warning.
"""

import frappe
from frappe.utils import getdate
from frappe.utils.caching import site_cache

# posthog provider
from .posthog import POSTHOG_HOST_FIELD, POSTHOG_PROJECT_FIELD
from .posthog import capture as ph_capture
from .posthog import capture_doc as _ph_capture_doc
from .posthog import init_telemetry as _init_ph_telemetry
from .posthog import is_enabled as is_posthog_enabled

# pulse provider
from .pulse.client import capture as pulse_capture
from .pulse.client import is_enabled as is_pulse_enabled


def add_bootinfo(bootinfo):
	bootinfo.telemetry_site_age = site_age()
	bootinfo.telemetry_provider = []

	if is_posthog_enabled():
		bootinfo.enable_telemetry = True
		bootinfo.telemetry_provider.append("posthog")
		bootinfo.posthog_host = frappe.conf.get(POSTHOG_HOST_FIELD)
		bootinfo.posthog_project_id = frappe.conf.get(POSTHOG_PROJECT_FIELD)

	if is_pulse_enabled():
		bootinfo.enable_telemetry = True
		bootinfo.telemetry_provider.append("pulse")


def capture(event, app, **kwargs):
	if is_posthog_enabled():
		ph_capture(event, app, **kwargs)

	if is_pulse_enabled():
		pulse_capture(event, app=app, **kwargs)


@site_cache(ttl=60 * 60 * 12)
def site_age():
	try:
		est_creation = frappe.db.get_value("User", "Administrator", "creation")
		return (getdate() - getdate(est_creation)).days + 1
	except Exception:
		pass


# for backward compatibility
init_telemetry = _init_ph_telemetry
capture_doc = _ph_capture_doc
