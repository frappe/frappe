# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

from functools import partial
from itertools import chain
from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.rate_limiter import rate_limit
from frappe.utils.caching import http_cache
from frappe.utils.safe_exec import (
	FrappeTransformer,
	get_keys_for_autocomplete,
	get_safe_globals,
	is_safe_exec_enabled,
	safe_exec,
)

if TYPE_CHECKING:
	from frappe.core.doctype.scheduled_job_type.scheduled_job_type import ScheduledJobType


class ServerScript(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		allow_guest: DF.Check
		api_method: DF.Data | None
		cron_format: DF.Data | None
		disabled: DF.Check
		doctype_event: DF.Literal[
			"Before Insert",
			"Before Validate",
			"Before Save",
			"After Insert",
			"After Save",
			"Before Rename",
			"After Rename",
			"Before Submit",
			"After Submit",
			"Before Cancel",
			"After Cancel",
			"Before Discard",
			"After Discard",
			"Before Delete",
			"After Delete",
			"Before Save (Submitted Document)",
			"After Save (Submitted Document)",
			"Before Print",
			"On Payment Authorization",
			"On Payment Paid",
			"On Payment Failed",
			"On Payment Charge Processed",
			"On Payment Mandate Charge Processed",
			"On Payment Mandate Acquisition Processed",
		]
		enable_rate_limit: DF.Check
		event_frequency: DF.Literal[
			"All",
			"Hourly",
			"Daily",
			"Weekly",
			"Monthly",
			"Yearly",
			"Hourly Long",
			"Daily Long",
			"Weekly Long",
			"Monthly Long",
			"Cron",
		]
		module: DF.Link | None
		rate_limit_count: DF.Int
		rate_limit_seconds: DF.Int
		reference_doctype: DF.Link | None
		script: DF.Code
		script_type: DF.Literal[
			"DocType Event", "Scheduler Event", "Permission Query", "API", "Workflow Task"
		]
	# end: auto-generated types

	def validate(self):
		frappe.only_for("Script Manager", True)
		self.check_if_compilable_in_restricted_context()

	def on_update(self):
		self.sync_scheduled_job_type()

	def clear_cache(self):
		frappe.client_cache.delete_value("server_script_map")
		return super().clear_cache()

	def on_trash(self):
		frappe.client_cache.delete_value("server_script_map")
		if self.script_type == "Scheduler Event":
			for job in self.scheduled_jobs:
				scheduled_job_type: ScheduledJobType = frappe.get_doc("Scheduled Job Type", job.name)
				scheduled_job_type.stopped = True
				scheduled_job_type.server_script = None
				scheduled_job_type.save()

	def get_code_fields(self):
		return {"script": "py"}

	@property
	def scheduled_jobs(self) -> list[dict[str, str]]:
		return frappe.get_all(
			"Scheduled Job Type",
			filters={"server_script": self.name},
			fields=["name", "stopped"],
		)

	def sync_scheduled_job_type(self):
		"""Create or update Scheduled Job Type documents for Scheduler Event Server Scripts"""

		def get_scheduled_job() -> "ScheduledJobType":
			if scheduled_script := frappe.db.get_value("Scheduled Job Type", {"server_script": self.name}):
				return frappe.get_doc("Scheduled Job Type", scheduled_script)
			else:
				return frappe.get_doc({"doctype": "Scheduled Job Type", "server_script": self.name})

		previous_script_type = self.get_value_before_save("script_type")
		if previous_script_type != self.script_type and previous_script_type == "Scheduler Event":
			get_scheduled_job().update({"stopped": 1}).save()
			return

		if self.script_type != "Scheduler Event" or not (
			self.has_value_changed("event_frequency")
			or self.has_value_changed("cron_format")
			or self.has_value_changed("disabled")
			or self.has_value_changed("script_type")
		):
			return

		get_scheduled_job().update(
			{
				"method": frappe.scrub(f"{self.name}-{self.event_frequency}"),
				"frequency": self.event_frequency,
				"cron_format": self.cron_format if self.event_frequency == "Cron" else "",
				"stopped": self.disabled,
			}
		).save()

		frappe.msgprint(_("Scheduled execution for script {0} has updated").format(self.name), alert=True)

	def check_if_compilable_in_restricted_context(self):
		"""Check compilation errors and send them back as warnings."""
		from RestrictedPython import compile_restricted

		try:
			compile_restricted(self.script, policy=FrappeTransformer)
		except Exception as e:
			frappe.msgprint(str(e), title=_("Compilation warning"))

	def execute_method(self) -> dict:
		"""Specific to API endpoint Server Scripts.

		Raise:
		        frappe.DoesNotExistError: If self.script_type is not API.
		        frappe.PermissionError: If self.allow_guest is unset for API accessed by Guest user.

		Return:
		        dict: Evaluate self.script with frappe.utils.safe_exec.safe_exec and return the flags set in its safe globals.
		"""

		if self.enable_rate_limit:
			# Wrap in rate limiter, required for specifying custom limits for each script
			# Note that rate limiter works on `cmd` which is script name
			limit = self.rate_limit_count or 5
			seconds = self.rate_limit_seconds or 24 * 60 * 60

			_fn = partial(execute_api_server_script, script=self)
			return rate_limit(limit=limit, seconds=seconds)(_fn)()
		else:
			return execute_api_server_script(self)

	def execute_doc(self, doc: Document):
		"""Specific to Document Event triggered Server Scripts

		Args:
		        doc (Document): Executes script with for a certain document's events
		"""
		safe_exec(
			self.script,
			_locals={"doc": doc},
			restrict_commit_rollback=True,
			script_filename=self.name,
		)

	def execute_scheduled_method(self):
		"""Specific to Scheduled Jobs via Server Scripts

		Raises:
		        frappe.DoesNotExistError: If script type is not a scheduler event
		"""
		if self.script_type != "Scheduler Event":
			raise frappe.DoesNotExistError

		safe_exec(self.script, script_filename=self.name)

	def get_permission_query_conditions(self, user: str) -> list[str]:
		"""Specific to Permission Query Server Scripts.

		Args:
		        user (str): Take user email to execute script and return list of conditions.

		Return:
		        list: Return list of conditions defined by rules in self.script.
		"""
		locals = {"user": user, "conditions": ""}
		safe_exec(self.script, None, locals, script_filename=self.name)
		if locals["conditions"]:
			return locals["conditions"]

	def execute_workflow_task(self, doc: Document):
		"""
		Specific to Workflow Tasks via Workflow Action Master
		"""
		if self.script_type != "Workflow Task":
			raise frappe.DoesNotExistError

		safe_exec(
			self.script,
			_locals={"doc": doc},
			script_filename=self.name,
		)


@frappe.whitelist()
@http_cache(max_age=10 * 60, stale_while_revalidate=6 * 60 * 60)
def get_autocompletion_items():
	"""Generate a list of autocompletion strings from the context dict
	that is used while executing a Server Script.

	e.g., ["frappe.utils.cint", "frappe.get_all", ...]
	"""

	return frappe.cache.get_value(
		"server_script_autocompletion_items",
		generator=lambda: list(
			chain.from_iterable(
				get_keys_for_autocomplete(key, value, meta="utils")
				for key, value in get_safe_globals().items()
			),
		),
	)


def execute_api_server_script(script: ServerScript, *args, **kwargs):
	# These are only added for compatibility with rate limiter.
	del args
	del kwargs

	if script.script_type != "API":
		raise frappe.DoesNotExistError

	# validate if guest is allowed
	if frappe.session.user == "Guest" and not script.allow_guest:
		raise frappe.PermissionError

	# output can be stored in flags
	_globals, _locals = safe_exec(script.script, script_filename=script.name)

	return _globals.frappe.flags


@frappe.whitelist()
def enabled() -> bool | None:
	if frappe.has_permission("Server Script"):
		return is_safe_exec_enabled()
