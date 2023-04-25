""" Basic telemetry for improving apps.

WARNING: Everything in this file should be treated "internal" and is subjected to change or get
removed without any warning.
"""
from contextlib import suppress

from posthog import Posthog

import frappe


def add_bootinfo(bootinfo):
	if not frappe.get_system_settings("enable_telemetry"):
		return

	bootinfo.posthog_host = frappe.conf.posthog_host
	bootinfo.posthog_project_id = frappe.conf.posthog_project_id
	bootinfo.enable_telemetry = True


def init_telemetry():
	"""Init posthog for server side telemetry."""
	if hasattr(frappe.local, "posthog"):
		return

	if not frappe.get_system_settings("enable_telemetry"):
		return

	posthog_host = frappe.conf.posthog_host
	posthog_project_id = frappe.conf.posthog_project_id

	if not posthog_host or not posthog_project_id:
		return

	with suppress(Exception):
		frappe.local.posthog = Posthog(posthog_project_id, host=posthog_host)


def capture(event, app):
	init_telemetry()
	ph: Posthog = getattr(frappe.local, "posthog", None)
	with suppress(Exception):
		ph and ph.capture(frappe.local.site, f"{app}_{event}")
