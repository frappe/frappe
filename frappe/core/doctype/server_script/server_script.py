# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import keyword
import re
from functools import partial
from itertools import chain
from typing import TYPE_CHECKING

from RestrictedPython.transformer import INSPECT_ATTRIBUTES

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.rate_limiter import rate_limit
from frappe.utils.caching import http_cache
from frappe.utils.password import get_decrypted_password
from frappe.utils.safe_exec import (
	UNSAFE_ATTRIBUTES,
	FrappeTransformer,
	get_keys_for_autocomplete,
	get_safe_globals,
	is_safe_exec_enabled,
	safe_exec,
)

if TYPE_CHECKING:
	from frappe.core.doctype.scheduled_job_type.scheduled_job_type import ScheduledJobType
	from frappe.core.doctype.server_script_variable.server_script_variable import ServerScriptVariable

VARIABLE_KEY_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


class ServerScript(Document):
	_DOCTYPE_NAME = "Server Script"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.server_script_variable.server_script_variable import ServerScriptVariable
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
		queue: DF.Literal["", "default", "short", "long"]
		rate_limit_count: DF.Int
		rate_limit_seconds: DF.Int
		reference_doctype: DF.Link | None
		script: DF.Code
		script_type: DF.Literal[
			"DocType Event", "Scheduler Event", "Permission Query", "API", "Workflow Task"
		]
		variables: DF.Table[ServerScriptVariable]
	# end: auto-generated types

	def validate(self):
		frappe.only_for("Script Manager", True)
		self.validate_variables()
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

	def validate_variables(self):
		keys = set()
		for variable in self.variables:
			if not VARIABLE_KEY_PATTERN.fullmatch(variable.key or "") or keyword.iskeyword(variable.key):
				frappe.throw(
					_(
						"Row #{0}: Key {1} must start with a letter and contain only letters, digits and underscores"
					).format(variable.idx, frappe.bold(variable.key)),
					title=_("Invalid Key"),
				)
			if (
				variable.key in UNSAFE_ATTRIBUTES
				or variable.key in INSPECT_ATTRIBUTES
				or variable.key.endswith("__roles__")
			):
				frappe.throw(
					_("Row #{0}: Key {1} is a reserved name").format(variable.idx, frappe.bold(variable.key)),
					title=_("Invalid Key"),
				)
			if variable.key in keys:
				frappe.throw(
					_("Row #{0}: Key {1} is already set").format(variable.idx, frappe.bold(variable.key)),
					title=_("Duplicate Key"),
				)
			keys.add(variable.key)

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
				should_create_log = self.event_frequency not in ("All", "Cron")
				return frappe.get_doc(
					{
						"doctype": "Scheduled Job Type",
						"server_script": self.name,
						"create_log": should_create_log,
					}
				)

		previous_script_type = self.get_value_before_save("script_type")
		if previous_script_type != self.script_type and previous_script_type == "Scheduler Event":
			get_scheduled_job().update({"stopped": 1}).save()
			return

		if self.script_type != "Scheduler Event" or not (
			self.has_value_changed("event_frequency")
			or self.has_value_changed("cron_format")
			or self.has_value_changed("queue")
			or self.has_value_changed("disabled")
			or self.has_value_changed("script_type")
		):
			return

		get_scheduled_job().update(
			{
				"method": frappe.scrub(f"{self.name}-{self.event_frequency}"),
				"frequency": self.event_frequency,
				"cron_format": self.cron_format if self.event_frequency == "Cron" else "",
				"queue": self.queue,
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
			limit = self.rate_limit_count or 5
			seconds = self.rate_limit_seconds or 24 * 60 * 60

			_fn = partial(execute_api_server_script, script=self)
			return rate_limit(limit=limit, seconds=seconds, endpoint=f"server_script:{self.name}")(_fn)()
		else:
			return execute_api_server_script(self)

	def execute_doc(self, doc: Document):
		"""Specific to Document Event triggered Server Scripts

		Args:
		        doc (Document): Executes script with for a certain document's events
		"""
		self.run_script(_locals={"doc": doc}, restrict_commit_rollback=True)

	def execute_scheduled_method(self):
		"""Specific to Scheduled Jobs via Server Scripts

		Raises:
		        frappe.DoesNotExistError: If script type is not a scheduler event
		"""
		if self.script_type != "Scheduler Event":
			raise frappe.DoesNotExistError

		self.run_script()

	def get_permission_query_conditions(self, user: str, active_child_tables=None) -> list[str]:
		"""Specific to Permission Query Server Scripts.

		Args:
		        user (str): Take user email to execute script and return list of conditions.
				active_child_tables (list, optional): A list of child table names involved in the current SQL query.

		Return:
		        list: Return list of conditions defined by rules in self.script.
		"""
		locals = {
			"user": user,
			"conditions": "",
			"active_child_tables": active_child_tables or [],
		}
		self.run_script(_locals=locals)
		if locals["conditions"]:
			return locals["conditions"]

	def execute_workflow_task(self, doc: Document):
		"""
		Specific to Workflow Tasks via Workflow Action Master
		"""
		if self.script_type != "Workflow Task":
			raise frappe.DoesNotExistError

		self.run_script(_locals={"doc": doc})

	def run_script(self, _locals: dict | None = None, restrict_commit_rollback: bool = False):
		# nosemgrep: frappe-codeinjection-eval
		return safe_exec(
			self.script,
			_locals=_locals,
			restrict_commit_rollback=restrict_commit_rollback,
			script_filename=self.name,
			env=ServerScriptEnv(self.variables),
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
	_globals, _locals = script.run_script()

	return _globals.frappe.flags


@frappe.whitelist()
def enabled() -> bool | None:
	if frappe.has_permission("Server Script"):
		return is_safe_exec_enabled()


class ServerScriptEnv:
	"""`frappe.env` of a Server Script. Values are decrypted on attribute access."""

	def __init__(self, variables: list["ServerScriptVariable"]):
		self._variables = {variable.key: variable for variable in variables}

	def __getattr__(self, key: str) -> str:
		if key.startswith("_"):
			raise AttributeError(key)

		if not (variable := self._variables.get(key)):
			frappe.throw(
				_("Environment variable {0} is not set in this Server Script").format(frappe.bold(key)),
				title=_("Missing Environment Variable"),
			)

		if value := get_decrypted_password(variable.doctype, variable.name, "value", raise_exception=False):
			return value

		if frappe.db.exists(
			"__Auth",
			{"doctype": variable.doctype, "name": variable.name, "fieldname": "value", "encrypted": 1},
		):
			return get_decrypted_password(variable.doctype, variable.name, "value")

		frappe.throw(
			_("Environment variable {0} has no saved value. Set it again in this Server Script").format(
				frappe.bold(key)
			),
			title=_("Missing Environment Variable"),
		)
