"""Basic telemetry for improving apps.

WARNING: Everything in this file should be treated "internal" and is subjected to change or get
removed without any warning.
"""

from contextlib import suppress

import frappe
from frappe.utils import getdate
from frappe.utils.caching import site_cache

# pulse provider
from .pulse.client import boot_config as pulse_boot_config
from .pulse.client import capture as pulse_capture
from .pulse.client import is_enabled as is_pulse_enabled


def add_bootinfo(bootinfo):
	bootinfo.telemetry_site_age = site_age()
	bootinfo.telemetry_provider = []

	if is_pulse_enabled():
		bootinfo.enable_telemetry = True
		bootinfo.telemetry_provider.append("pulse")
		bootinfo.telemetry = pulse_boot_config()


def capture(event, app, **kwargs):
	if is_pulse_enabled():
		pulse_capture(event, app=app, **kwargs)


def capture_doc(doc, action):
	with suppress(Exception):
		age = site_age()
		if not age or age > 15:
			return

		if doc.get("__islocal") or not doc.get("name"):
			capture("document_created", "frappe", properties={"doctype": doc.doctype, "action": "Insert"})
		else:
			capture("document_modified", "frappe", properties={"doctype": doc.doctype, "action": action})


@site_cache(ttl=60 * 60 * 12)
def site_age():
	try:
		est_creation = frappe.db.get_value("User", "Administrator", "creation")
		return (getdate() - getdate(est_creation)).days + 1
	except Exception:
		pass
