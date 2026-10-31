# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Flow Triggers defined in code."""

from __future__ import annotations

import sys

import frappe
from frappe import _
from frappe.flow.lib.agent import with_app_prefix
from frappe.flow.utils.system_generated import skip_if_invalid


def sync_triggers(_app: str | None = None) -> None:
	"""Write every trigger the installed apps declare through the `flow_triggers` hook, whose
	entries name functions returning a list of Triggers, and delete the app triggers no longer
	declared. Runs after migrate and app installs, and once the Assistant exists. A trigger that
	cannot be written is skipped and logged; one whose agent is missing waits for a later sync."""
	declared: set[str] = set()
	for path in frappe.get_hooks("flow_triggers"):
		triggers = None
		with skip_if_invalid(f"Flow Triggers of {path} skipped"):
			triggers = frappe.get_attr(path)()
		if triggers is None:
			# keep what the app shipped before rather than delete it
			app = path.split(".", 1)[0]
			declared.update(
				frappe.get_all("Flow Trigger", {"is_system_generated": 1, "app": app}, pluck="name")
			)
			continue
		for trigger in triggers:
			declared.add(trigger.name)
			with skip_if_invalid(f"Flow Trigger {trigger.name} skipped"):
				trigger.sync()
	for name in frappe.get_all("Flow Trigger", {"is_system_generated": 1}, pluck="name"):
		if name not in declared:
			# force: its Flow Runs keep the name
			frappe.delete_doc("Flow Trigger", name, ignore_permissions=True, force=True)


class Trigger:
	"""A Flow Trigger defined in code.

	Flow writes the triggers listed under the `flow_triggers` hook as system-generated Flow
	Triggers named `<app>/<title>`, after the app whose code builds them. They arrive switched
	on: the desk can switch them off, nothing else. Pass `doctype` and `doc_event` to run on a
	document event, or `cron` to run on a schedule. `agent` is this app's agent by name, or
	another's as `<app>/<name>`, like ASSISTANT_AGENT_NAME for the built-in Assistant. `run_as`
	is a user the app creates with only the roles the trigger needs; without it the trigger runs
	as Administrator.
	"""

	def __init__(
		self,
		*,
		title: str,
		agent: str,
		prompt: str,
		doctype: str | None = None,
		doc_event: str | None = None,
		cron: str | None = None,
		condition: str | None = None,
		run_as: str | None = None,
	):
		# the calling module's app, as Agent finds it
		self.app = sys._getframe(1).f_globals["__name__"].split(".", 1)[0]
		self.name = f"{self.app}/{title}"
		self.agent = with_app_prefix(self.app, agent)
		self.prompt = prompt
		self.doctype = doctype
		self.doc_event = doc_event
		self.cron = cron
		self.condition = condition
		self.run_as = run_as

	def sync(self) -> None:
		"""Write this definition to the site, keeping whether the site switched it on. Writes
		nothing while the agent is missing."""
		if self.cron and self.doctype:
			frappe.throw(
				_("Flow Trigger {0} needs a doctype or a cron, not both.").format(self.name),
				title=_("Invalid Trigger"),
			)
		if not frappe.db.exists("Flow Agent", self.agent):
			return
		if frappe.db.exists("Flow Trigger", self.name):
			doc = frappe.get_doc("Flow Trigger", self.name)
		else:
			doc = frappe.get_doc(
				{
					"doctype": "Flow Trigger",
					"title": self.name,
					"app": self.app,
					"enabled": 1,
					"is_system_generated": 1,
				}
			)
		doc.update(
			{
				"agent": self.agent,
				"event": "Scheduled" if self.cron else "DocType Event",
				"target_doctype": self.doctype,
				"doc_event": self.doc_event,
				"cron_expression": self.cron,
				"condition": self.condition,
				"prompt_template": self.prompt,
				"run_as": self.run_as,
			}
		)
		doc.save(ignore_permissions=True)
