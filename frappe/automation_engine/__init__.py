# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from contextlib import contextmanager

import frappe


def emit(event, doc=None, payload=None, correlation_key=None):
	"""Publish a registered application event to flows and waiting runs."""
	from frappe.automation_engine.events import emit as emit_event

	return emit_event(event, doc=doc, payload=payload, correlation_key=correlation_key)


def is_enabled() -> bool:
	"""Return whether automations may run for this request."""
	if frappe.flags.get("skip_automations"):
		return False
	return not frappe.conf.get("automation_disabled")


@contextmanager
def skip_automations():
	"""Suppress all automation dispatch within the block."""
	previous = frappe.flags.get("skip_automations")
	frappe.flags.skip_automations = True
	try:
		yield
	finally:
		frappe.flags.skip_automations = previous
