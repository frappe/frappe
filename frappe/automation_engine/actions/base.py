# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

"""Action base class and hook-driven registry.

Each action declares a `params_schema` that drives both server-side validation and the
shared Vue builder. Apps contribute actions via the `automation_actions` hook (a list of
dotted paths to AutomationAction subclasses).
"""

import frappe
from frappe import _


class AutomationParamError(frappe.ValidationError):
	"""Raised when an action's params are invalid; carries the offending fieldname."""

	def __init__(self, message, fieldname=None):
		self.fieldname = fieldname
		super().__init__(message)


class StopAutomation(Exception):
	"""Raised by an action to pause the run (wait/resume). Executed in Phase 2."""


class AutomationAction:
	action_type: str = ""
	label: str = ""
	description: str = ""
	applicable_doctypes: list | None = None  # None = all doctypes
	params_schema: list = []

	def validate(self, params: dict, doctype: str):
		"""Override to validate params against `doctype`; raise AutomationParamError."""

	def execute(self, doc, params: dict, context: dict):
		"""Run the action against `doc`. Return a short detail string for the run log."""
		raise NotImplementedError

	def as_dict(self) -> dict:
		return {
			"action_type": self.action_type,
			"label": self.label,
			"description": self.description,
			"applicable_doctypes": self.applicable_doctypes,
			"params_schema": self.params_schema,
		}


def get_action_registry() -> dict:
	"""Return {action_type: AutomationAction instance}, memoized on frappe.local."""
	if getattr(frappe.local, "automation_actions", None) is not None:
		return frappe.local.automation_actions

	registry: dict = {}
	for cls in _iter_action_classes():
		action = cls()
		if action.action_type in registry:
			frappe.throw(_("Duplicate automation action_type: {0}").format(action.action_type))
		registry[action.action_type] = action

	frappe.local.automation_actions = registry
	return registry


def get_action(action_type: str) -> AutomationAction:
	action = get_action_registry().get(action_type)
	if not action:
		frappe.throw(_("Unknown automation action: {0}").format(action_type))
	return action


def _iter_action_classes():
	from frappe.automation_engine.actions.core import CORE_ACTIONS

	yield from CORE_ACTIONS
	for path in frappe.get_hooks("automation_actions"):
		yield frappe.get_attr(path)
