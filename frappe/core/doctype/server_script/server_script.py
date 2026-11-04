# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import builtins
import keyword
import os
import re
from functools import partial
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

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
	ServerScriptNotEnabled,
	UnavailableEnv,
	get_keys_for_autocomplete,
	get_safe_globals,
	is_safe_exec_enabled,
	safe_exec,
)

if TYPE_CHECKING:
	from frappe.core.doctype.scheduled_job_type.scheduled_job_type import ScheduledJobType
	from frappe.core.doctype.server_script_variable.server_script_variable import ServerScriptVariable

VARIABLE_KEY_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]*")

_compiled_file_cache: dict[str, tuple[int, object]] = {}

FILE_SCRIPT_TRIGGER_FIELDS = (
	"script_type",
	"reference_doctype",
	"doctype_event",
	"api_method",
	"allow_guest",
	"event_frequency",
	"cron_format",
	"enable_rate_limit",
	"rate_limit_count",
	"rate_limit_seconds",
)


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
		script_source: DF.Literal["Database", "File"]
		script_type: DF.Literal[
			"DocType Event", "Scheduler Event", "Permission Query", "API", "Workflow Task"
		]
		variables: DF.Table[ServerScriptVariable]
	# end: auto-generated types

	def validate(self):
		frappe.only_for("Script Manager", True)
		self.validate_script_source_change()
		self.validate_file_script_triggers()
		self.validate_variables()
		if self.script_source == "File":
			self.get_file_path()
			self.script = ""
			return
		if not self.script:
			frappe.throw(_("Script is required for Database scripts"), frappe.MandatoryError)
		self.check_if_compilable_in_restricted_context()

	def after_delete(self):
		if self.script_source != "File":
			return
		path = self.get_file_path()
		if os.path.exists(path):
			os.remove(path)

	def validate_file_script_triggers(self):
		"""File code runs unrestricted, so only Administrator changes what runs it and who can."""
		if self.script_source != "File" or self.is_new() or frappe.session.user == "Administrator":
			return
		if changed := [field for field in FILE_SCRIPT_TRIGGER_FIELDS if self.has_value_changed(field)]:
			frappe.throw(
				_("Only Administrator can change {0} of a File script").format(
					", ".join(_(self.meta.get_label(field)) for field in changed)
				),
				frappe.PermissionError,
			)

	def validate_script_source_change(self):
		"""File is one-way: Database -> File moves the body to disk, never back."""
		before = self.get_doc_before_save()
		if not before:
			return
		was_file = before.script_source == "File"
		if was_file and self.script_source != "File":
			frappe.throw(_("A File script cannot be switched back to Database"))
		if not was_file and self.script_source == "File":
			if frappe.session.user != "Administrator":
				frappe.throw(_("Only Administrator can switch a script to File"), frappe.PermissionError)
			path = self.get_file_path()
			if os.path.exists(path):
				frappe.throw(_("{0} already exists. Remove it before switching to File").format(path))
			self.flags.body_to_migrate = self.script or before.script

	def onload(self):
		"""Show a File script's body read-only; `validate` blanks it again on save."""
		if self.script_source != "File":
			return
		path = self.get_file_path()
		self.set_onload("file_path", path)
		self.set_onload("editor_url", self.get_editor_url())
		if "Script Manager" in frappe.get_roles() and os.path.exists(path):
			self.script = Path(path).read_text()

	def get_editor_url(self) -> str | None:
		"""Pilot's code editor for this site's scripts, opened at this script's file."""
		pilot_url = frappe.conf.get("cloud_server_url") or frappe.conf.get("pilot_endpoint")
		if not pilot_url:
			return None
		site = quote(frappe.local.site, safe="")
		file_name = quote(f"{self.name}.py", safe="")
		return f"{pilot_url.rstrip('/')}/editor/site/{site}?open={file_name}"

	def on_update(self):
		self.sync_scheduled_job_type()
		self.ensure_file_stub()

	def get_file_path(self) -> str:
		"""Where this script's body lives on disk when `script_source` is "File".

		Flat by `name` only (the doctype's own primary key, already globally
		unique) — trigger fields stay DB-resident and are never encoded into
		the path, so retargeting a script's event/doctype never moves its file.
		"""
		if not self.name or Path(self.name).name != self.name or self.name in (".", ".."):
			frappe.throw(
				_("Server Script name {0} cannot be used as a file name").format(self.name),
				frappe.ValidationError,
			)
		return frappe.get_site_path("server_scripts", f"{self.name}.py")

	def ensure_file_stub(self):
		"""Scaffold the backing file on first save. Never overwrites an existing file."""
		if self.script_source != "File":
			return
		path = self.get_file_path()
		if os.path.exists(path):
			return
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path, "w") as f:
			f.write(self.flags.body_to_migrate or self.get_file_stub_content())

	def get_compiled_file_code(self):
		"""Compile the backing file, recompiling only when its mtime changes."""
		path = self.get_file_path()
		try:
			mtime = os.stat(path).st_mtime_ns
		except FileNotFoundError:
			frappe.throw(
				_("Server Script {0} is File-sourced but {1} does not exist").format(self.name, path),
				frappe.DoesNotExistError,
			)
		cached = _compiled_file_cache.get(path)
		if cached and cached[0] == mtime:
			return cached[1]
		with open(path) as f:
			source = f.read()
		try:
			code = compile(source, f"<server_script_file: {frappe.scrub(self.name)}>", "exec")
		except SyntaxError as e:
			frappe.throw(
				_("Server Script {0} has a syntax error in {1}: {2}").format(self.name, path, e),
				frappe.ValidationError,
			)
		_compiled_file_cache[path] = (mtime, code)
		return code

	def run_script(self, _locals: dict | None = None, restrict_commit_rollback: bool = False):
		"""Run the body from the DB (restricted) or from its file (plain Python, real `frappe`).

		File scripts share one namespace, so imports and helper functions work; results are
		read back into `_locals`. `frappe.env` holds the variables while the script runs."""
		env = ServerScriptEnv(self.variables)
		if self.script_source != "File":
			# nosemgrep: frappe-codeinjection-eval
			return safe_exec(
				self.script,
				_locals=_locals,
				restrict_commit_rollback=restrict_commit_rollback,
				script_filename=self.name,
				env=env,
			)
		if not is_safe_exec_enabled():
			frappe.throw(_("Server Scripts are disabled."), ServerScriptNotEnabled)
		namespace = {"__builtins__": builtins, "frappe": frappe, "_": _, **(_locals or {})}
		previous_env = getattr(frappe.local, "server_script_env", UnavailableEnv())
		request_flags = vars(frappe)["flags"]
		frappe.local.server_script_env = env
		frappe.db._disable_transaction_control += int(restrict_commit_rollback)
		try:
			exec(self.get_compiled_file_code(), namespace)
		finally:
			frappe.db._disable_transaction_control -= int(restrict_commit_rollback)
			frappe.local.server_script_env = previous_env
			replaced_flags = vars(frappe)["flags"] is not request_flags
			frappe.flags = request_flags
		if replaced_flags:
			frappe.throw(
				_("File Server Scripts cannot replace frappe.flags. Return API results with {0}.").format(
					"<code>frappe.response['message']</code>"
				)
			)
		if _locals is not None:
			_locals.update({key: namespace[key] for key in _locals})
		return namespace, _locals

	def get_file_stub_content(self) -> str:
		trigger = {
			"DocType Event": f"doctype_event={self.doctype_event}, reference_doctype={self.reference_doctype}",
			"Scheduler Event": f"event_frequency={self.event_frequency}",
			"API": f"api_method={self.api_method}",
			"Permission Query": f"reference_doctype={self.reference_doctype}",
			"Workflow Task": "workflow task",
		}.get(self.script_type, "")
		return (
			f"# Server Script: {self.name}\n"
			f"# script_type={self.script_type} {trigger}\n"
			f"# Trigger metadata lives on the Server Script record in the DB; this file is the body only.\n\n"
		)

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

	if script.script_source == "File":
		# the real frappe.flags belongs to the request; File scripts answer via frappe.response
		return {}
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


def delete_file_script(name: str):
	"""Delete a File Server Script's record and file, or just an orphaned file. Not whitelisted."""
	if frappe.db.exists("Server Script", name):
		script = frappe.get_doc("Server Script", name)
		if script.script_source != "File":
			frappe.throw(_("Server Script {0} is not File-sourced").format(name))
		script.delete()
		return
	path = frappe.get_doc({"doctype": "Server Script", "name": name}).get_file_path()
	if os.path.exists(path):
		os.remove(path)
