# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

DOC_EVENTS = frozenset({"after_insert", "on_update", "on_submit", "on_cancel", "on_trash"})


class FlowTrigger(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		agent: DF.Link
		auto_approve: DF.Check
		condition: DF.Code | None
		cron_expression: DF.Data | None
		doc_event: DF.Literal[None, "after_insert", "on_update", "on_submit", "on_cancel", "on_trash"]
		enabled: DF.Check
		event: DF.Literal["DocType Event", "Scheduled"]
		last_fired_at: DF.Datetime | None
		prompt_template: DF.Code
		run_as: DF.Link | None
		target_doctype: DF.Link | None
		title: DF.Data
	# end: auto-generated types

	def validate(self):
		self._validate_event_fields()
		self._validate_cron()
		self._validate_condition()
		self._validate_template()
		self._validate_run_as()

	def _validate_run_as(self):
		if not self.run_as:
			return
		if self.run_as == "Guest" or not frappe.db.get_value("User", self.run_as, "enabled"):
			frappe.throw(
				_("Run As must be an enabled user."),
				title=_("Invalid Run As"),
			)

	def _validate_event_fields(self):
		if self.event == "DocType Event":
			if not self.target_doctype:
				frappe.throw(_("Target DocType is required for DocType Event triggers."))
			if not self.doc_event:
				frappe.throw(_("Doc Event is required for DocType Event triggers."))
			if self.doc_event not in DOC_EVENTS:
				frappe.throw(_("Invalid Doc Event: {0}").format(self.doc_event))
		elif self.event == "Scheduled" and not self.cron_expression:
			frappe.throw(_("Cron Expression is required for Scheduled triggers."))

	def _validate_cron(self):
		if self.event != "Scheduled" or not self.cron_expression:
			return
		from croniter import CroniterBadCronError, croniter

		try:
			croniter(self.cron_expression)
		except (CroniterBadCronError, ValueError) as e:
			frappe.throw(_("Invalid cron expression: {0}").format(e), title=_("Invalid Cron"))

	def _validate_condition(self):
		from flow.utils.conditions import validate_condition

		validate_condition(self.condition)

	def _validate_template(self):
		from jinja2 import TemplateSyntaxError
		from jinja2.sandbox import SandboxedEnvironment

		try:
			SandboxedEnvironment().parse(self.prompt_template or "")
		except TemplateSyntaxError as e:
			frappe.throw(_("Invalid Jinja template: {0}").format(e), title=_("Invalid Template"))
