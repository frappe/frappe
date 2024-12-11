# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

from functools import partial
from itertools import chain

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.rate_limiter import rate_limit
from frappe.utils.safe_exec import (
	FrappeTransformer,
	get_keys_for_autocomplete,
	get_safe_globals,
	is_safe_exec_enabled,
	safe_exec,
)


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
			"Before Delete",
			"After Delete",
			"Before Save (Submitted Document)",
			"After Save (Submitted Document)",
			"Before Print",
			"On Payment Authorization",
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
		script_type: DF.Literal["DocType Event", "Scheduler Event", "Permission Query", "API"]

	# end: auto-generated types
	def validate(self):
		frappe.only_for("Script Manager", True)
		self.sync_scheduled_jobs()
		self.clear_scheduled_events()
		self.check_if_compilable_in_restricted_context()

	def on_update(self):
		self.sync_scheduler_events()

	def clear_cache(self):
		frappe.cache.delete_value("server_script_map")
		return super().clear_cache()

	def on_trash(self):
		frappe.cache.delete_value("server_script_map")
		if self.script_type == "Scheduler Event":
			for job in self.scheduled_jobs:
				frappe.delete_doc("Scheduled Job Type", job.name)

	def get_code_fields(self):
		return {"script": "py"}

	@property
	def scheduled_jobs(self) -> list[dict[str, str]]:
		return frappe.get_all(
			"Scheduled Job Type",
			filters={"server_script": self.name},
			fields=["name", "stopped"],
		)

	def sync_scheduled_jobs(self):
		"""Sync Scheduled Job Type statuses if Server Script's disabled status is changed"""
		if self.script_type != "Scheduler Event" or not self.has_value_changed("disabled"):
			return

		for scheduled_job in self.scheduled_jobs:
			if bool(scheduled_job.stopped) != bool(self.disabled):
				job = frappe.get_doc("Scheduled Job Type", scheduled_job.name)
				job.stopped = self.disabled
				job.save()

	def sync_scheduler_events(self):
		"""Create or update Scheduled Job Type documents for Scheduler Event Server Scripts"""
		if not self.disabled and self.event_frequency and self.script_type == "Scheduler Event":
			cron_format = self.cron_format if self.event_frequency == "Cron" else None
			setup_scheduler_events(
				script_name=self.name, frequency=self.event_frequency, cron_format=cron_format
			)

	def clear_scheduled_events(self):
		"""Deletes existing scheduled jobs by Server Script if self.event_frequency or self.cron_format has changed"""
		if (
			self.script_type == "Scheduler Event"
			and (self.has_value_changed("event_frequency") or self.has_value_changed("cron_format"))
		) or (self.has_value_changed("script_type") and self.script_type != "Scheduler Event"):
			for scheduled_job in self.scheduled_jobs:
				frappe.delete_doc("Scheduled Job Type", scheduled_job.name, delete_permanently=1)

	def check_if_compilable_in_restricted_context(self):
		"""Check compilation errors and send them back as warnings."""
		from RestrictedPython import compile_restricted

		try:
			compile_restricted(self.script, policy=FrappeTransformer)
		except Exception as e:
			frappe.msgprint(str(e), title=_("Compilation warning"))

	def execute_method(self) -> dict:
		"""Specific to API endpoint Server Scripts

		Raises:
		        frappe.DoesNotExistError: If self.script_type is not API
		        frappe.PermissionError: If self.allow_guest is unset for API accessed by Guest user

		Returns:
		        dict: Evaluates self.script with frappe.utils.safe_exec.safe_exec and returns the flags set in it's safe globals
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
		"""Specific to Permission Query Server Scripts

		Args:
		        user (str): Takes user email to execute script and return list of conditions

		Returns:
		        list: Returns list of conditions defined by rules in self.script
		"""
		locals = {"user": user, "conditions": ""}
		safe_exec(self.script, None, locals, script_filename=self.name)
		if locals["conditions"]:
			return locals["conditions"]

	@frappe.whitelist()
	def get_autocompletion_items(self):
		"""Generates a list of a autocompletion strings from the context dict
		that is used while executing a Server Script.

		Returns:
		        list: Returns list of autocompletion items.
		        For e.g., ["frappe.utils.cint", "frappe.get_all", ...]
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


def setup_scheduler_events(script_name: str, frequency: str, cron_format: str | None = None):
	"""Creates or Updates Scheduled Job Type documents based on the specified script name and frequency

	Args:
	        script_name (str): Name of the Server Script document
	        frequency (str): Event label compatible with the Frappe scheduler
	"""
	method = frappe.scrub(f"{script_name}-{frequency}")
	scheduled_script = frappe.db.get_value("Scheduled Job Type", {"method": method})

	if not scheduled_script:
		frappe.get_doc(
			{
				"doctype": "Scheduled Job Type",
				"method": method,
				"frequency": frequency,
				"server_script": script_name,
				"cron_format": cron_format,
			}
		).insert()

		frappe.msgprint(_("Enabled scheduled execution for script {0}").format(script_name))

	else:
		doc = frappe.get_doc("Scheduled Job Type", scheduled_script)

		if doc.frequency == frequency:
			return

		doc.frequency = frequency
		doc.cron_format = cron_format
		doc.save()

		frappe.msgprint(_("Scheduled execution for script {0} has updated").format(script_name))


def execute_api_server_script(script=None, *args, **kwargs):
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
