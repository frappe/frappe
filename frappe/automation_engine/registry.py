# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

"""Cached lookup of automation rules, keyed per-doctype.

Reuses frappe.client_cache (the frappe.local + redis two-tier cache with cross-process
invalidation already solved), mirroring the `notifications::{doctype}` pattern in
Document.run_notifications. Per-doctype keys keep invalidation and deserialization scoped
to a single doctype; the empty list is cached too, so the no-op path stays a local dict hit.
"""

import frappe

REGISTRY_KEY = "automations::{}"
EVENTS_KEY = "automations::_events"

# Trigger types that fire from a document lifecycle event (matched in dispatch).
DOC_TRIGGER_TYPES = (
	"Doc Created",
	"Doc Updated",
	"Field Value Changed",
	"Doc Deleted",
	"Doc Submitted",
	"Doc Cancelled",
)

# Fields dispatch needs to match a rule - actions are loaded later by the runner.
RULE_FIELDS = (
	"name",
	"trigger_type",
	"trigger_field",
	"from_value",
	"to_value",
	"filters",
	"condition",
	"revalidate_on_run",
	"stop_on_error",
)


def get_automations_for(doctype: str) -> list:
	"""Return enabled doc-triggered automations for `doctype` (client-cached per doctype)."""
	return frappe.client_cache.get_value(
		REGISTRY_KEY.format(doctype), generator=lambda: _build_automations_for(doctype)
	)


def _build_automations_for(doctype: str) -> list:
	try:
		return frappe.get_all(
			"Automation Flow",
			filters={
				"enabled": 1,
				"document_type": doctype,
				"trigger_type": ("in", DOC_TRIGGER_TYPES),
			},
			fields=RULE_FIELDS,
		)
	except (frappe.DoesNotExistError, frappe.db.TableMissingError):
		return []


def get_custom_event_map() -> dict:
	"""Return {event_name: [rule meta]} for enabled Custom Event automations (global)."""
	return frappe.client_cache.get_value(EVENTS_KEY, generator=_build_custom_event_map)


def _build_custom_event_map() -> dict:
	try:
		rules = frappe.get_all(
			"Automation Flow",
			filters={"enabled": 1, "trigger_type": "Custom Event"},
			fields=(*RULE_FIELDS, "custom_event", "document_type"),
		)
	except (frappe.DoesNotExistError, frappe.db.TableMissingError):
		return {}
	event_map: dict = {}
	for rule in rules:
		event_map.setdefault(rule.custom_event, []).append(rule)
	return event_map


def clear_automation_cache(doctype: str | None = None):
	"""Invalidate the cached rule map. Pass a doctype to clear just that entry."""
	if doctype:
		frappe.client_cache.delete_value(REGISTRY_KEY.format(doctype))
		frappe.client_cache.delete_value(EVENTS_KEY)
	else:
		frappe.client_cache.delete_keys(REGISTRY_KEY.format(""))
	_clear_request_caches()


def _clear_request_caches():
	"""Registered providers and derived relationships are cached per request, and both follow
	from hooks and schema - installing an app or editing a DocType has to invalidate them."""
	from frappe.automation_engine.relationships import _providers
	from frappe.automation_engine.schema_relationships import _ignored, derived_definitions

	cache = getattr(frappe.local, "request_cache", None)
	for func in (_providers, derived_definitions, _ignored):
		if cache is not None:
			cache.pop(getattr(func, "__wrapped__", func), None)
