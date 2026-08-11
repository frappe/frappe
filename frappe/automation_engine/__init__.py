# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from contextlib import contextmanager

import frappe

# Queue rows that still owe work. A row waiting on a future run_after sits in Scheduled so
# the list view can tell "waiting for its time" apart from "waiting for a worker"; it moves
# to Pending once it comes due. Both are claimable, so the drainer spans the pair.
WAITING_STATES = ("Pending", "Scheduled")


def queue_status(run_after=None) -> str:
	"""Resting status for a queue row with this run_after."""
	if run_after and frappe.utils.get_datetime(run_after) > frappe.utils.now_datetime():
		return "Scheduled"
	return "Pending"


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
