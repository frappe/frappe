# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from contextlib import contextmanager

import frappe

SETTINGS = "Automation Settings"

DEFAULTS = frappe._dict(
	disable_automations=0,
	max_depth=3,
	failure_threshold=10,
	stale_running_minutes=30,
	max_attempts=3,
	drain_seconds=0,
	commit_every=50,
	queue_retention_days=7,
	step_output_limit=65536,
	event_payload_limit=65536,
	allow_unregistered_events=0,
)

# Zero is meaningful for these; everywhere else it reads as "unset" and the default applies.
ZERO_IS_MEANINGFUL = frozenset({"disable_automations", "drain_seconds", "allow_unregistered_events"})


def settings():
	"""Automation Settings, or the defaults while the single is not installed yet.

	Read on every document save, so it has to survive install and migrate.
	"""
	try:
		return frappe.get_cached_doc(SETTINGS)
	except (frappe.DoesNotExistError, frappe.db.TableMissingError):
		return DEFAULTS


def get(fieldname: str):
	"""Value of a setting, falling back to its default when unset."""
	value = settings().get(fieldname)
	if value in (None, "") or (not value and fieldname not in ZERO_IS_MEANINGFUL):
		return DEFAULTS[fieldname]
	return value


def is_enabled() -> bool:
	"""Return whether automations may run for this request."""
	if frappe.flags.get("skip_automations"):
		return False
	# site_config wins over the single: stopping automations must not need a working database.
	if frappe.conf.get("automation_disabled"):
		return False
	return not get("disable_automations")


@contextmanager
def skip_automations():
	"""Suppress all automation dispatch within the block."""
	previous = frappe.flags.get("skip_automations")
	frappe.flags.skip_automations = True
	try:
		yield
	finally:
		frappe.flags.skip_automations = previous
