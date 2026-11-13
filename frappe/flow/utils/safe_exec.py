# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""A permission-respecting sandbox for Flow's `execute` tool.

Reuses frappe's RestrictedPython machinery (compilation, guards, flags) but exposes
an allowlisted namespace where every data function enforces the current user's
permissions. Functions that bypass permissions — raw SQL, the query builder,
`db.set_value`, `get_all` — are left out entirely.
"""

from __future__ import annotations

import inspect
import json
import mimetypes
from typing import TYPE_CHECKING, Any, NoReturn

import RestrictedPython.Guards
from RestrictedPython import safe_globals

import frappe
from frappe import _
from frappe.core.doctype.file.utils import find_file_by_url
from frappe.core.utils import html2text
from frappe.utils.background_jobs import enqueue
from frappe.utils.inplacevar import protected_inplacevar
from frappe.utils.safe_exec import (
	SAFE_DATA_UTILS,
	SAFE_EXCEPTIONS,
	SAFE_ORJSON,
	SERVER_SCRIPT_FILE_PREFIX,
	FrappePrintCollector,
	NamespaceDict,
	_compile_code,
	_getattr_for_safe_exec,
	_getitem,
	_write,
	call_whitelisted_function,
	get_python_builtins,
	is_job_queued,
	safe_enqueue,
	safe_exec_flags,
	safer_get_meta,
	safer_log_error,
)

if TYPE_CHECKING:
	from frappe.flow.lib.tool import ToolContext


def safe_exec(
	script: str,
	_globals: dict | None = None,
	_locals: dict | None = None,
	*,
	script_filename: str | None = None,
	tool_context: ToolContext | None = None,
):
	from frappe.utils.safe_exec import ServerScriptNotEnabled, is_safe_exec_enabled

	if not is_safe_exec_enabled():
		frappe.throw(
			_("Server Scripts are disabled on this bench, so code cannot run here."),
			ServerScriptNotEnabled,
			title=_("Server Scripts Disabled"),
		)

	exec_globals = get_flow_safe_globals(tool_context=tool_context)
	if _globals:
		exec_globals.update(_globals)

	filename = SERVER_SCRIPT_FILE_PREFIX
	if script_filename:
		filename += f": {frappe.scrub(script_filename)}"

	with safe_exec_flags():
		# compiled by RestrictedPython, as frappe.utils.safe_exec does
		# nosemgrep: frappe-codeinjection-eval
		exec(_compile_code(script, filename=filename), exec_globals, _locals)

	return exec_globals, _locals


def _gated_get_doc(*args: Any, **kwargs: Any) -> dict:
	if len(args) == 2:
		args, kwargs = args[:1], {**kwargs, "name": args[1]}
	# anything but a name is filters: search them only among readable records
	name = kwargs.get("name")
	if args and name is not None and not isinstance(name, str | int):
		kwargs["name"] = _readable_name(args[0], name)
	doc = frappe.get_doc(*args, **kwargs)
	doc.check_permission("read")
	doc.apply_fieldlevel_read_permissions()
	return doc.as_dict()


def _gated_get_last_doc(doctype: str, filters=None, order_by: str = "creation desc", **kwargs: Any) -> dict:
	return _gated_get_doc(doctype, _readable_name(doctype, filters, order_by), **kwargs)


def _readable_name(doctype: str, filters, order_by: str = "creation desc") -> str:
	names = frappe.get_list(doctype, filters=filters, order_by=order_by, limit=1, pluck="name")
	if not names:
		raise frappe.DoesNotExistError(doctype=doctype)
	return names[0]


def _gated_get_meta(doctype: str, cached: bool = True) -> dict | None:
	if not frappe.has_permission(doctype, "read"):
		raise frappe.PermissionError(_("No permission to read {0}").format(doctype))
	return safer_get_meta(doctype, cached)


def _gated_get_print(doctype=None, name=None, *args: Any, **kwargs: Any):
	if doctype and name and not frappe.has_permission(doctype, "read", name):
		raise frappe.PermissionError(_("No permission to read {0} {1}").format(doctype, name))
	return frappe.get_print(doctype, name, *args, **kwargs)


def _gated_attach_print(doctype: str, name: str, *args: Any, **kwargs: Any):
	if not frappe.has_permission(doctype, "read", name):
		raise frappe.PermissionError(_("No permission to read {0} {1}").format(doctype, name))
	return frappe.attach_print(doctype, name, *args, **kwargs)


# job options: the queues are shared by every site on the bench
_ENQUEUE_OPTIONS = frozenset(inspect.signature(enqueue).parameters) - {"method", "kwargs"}


def _gated_enqueue(function: str, **kwargs: Any):
	if options := sorted(_ENQUEUE_OPTIONS & set(kwargs)):
		frappe.throw(
			_("frappe.enqueue takes only the function and its arguments here, not {0}.").format(
				", ".join(options)
			)
		)
	return safe_enqueue(function, **kwargs)


def _gated_sendmail(*args: Any, attachments: list | None = None, **kwargs: Any):
	return frappe.sendmail(*args, attachments=[_readable_attachment(a) for a in attachments or []], **kwargs)


def _readable_attachment(attachment: dict) -> dict:
	"""The email queue fetches file and print attachments as Administrator, so check them now."""
	attachment = dict(attachment)
	fid, file_url = attachment.pop("fid", None), attachment.pop("file_url", None)
	if fid or file_url:
		file = frappe.get_doc("File", str(fid)) if fid else find_file_by_url(str(file_url))
		if not (file and file.is_downloadable()):
			raise frappe.PermissionError(_("No permission to read file {0}").format(fid or file_url))
		attachment["fid"] = file.name  # the queue fetches the file checked here
	if attachment.get("print_format_attachment"):
		doctype, name = attachment.get("doctype"), attachment.get("name")
		if not (
			isinstance(doctype, str)
			and isinstance(name, str)
			and frappe.has_permission(doctype, "read", name)
		):
			raise frappe.PermissionError(_("No permission to read {0} {1}").format(doctype, name))
		attachment.pop("doc", None)  # print the checked record itself
	return attachment


def _permissioned_get_list(doctype, *args, **kwargs):
	for unsafe in ("ignore_permissions", "ignore_user_permissions", "user"):
		kwargs.pop(unsafe, None)
	return frappe.get_list(
		doctype,
		*args,
		ignore_permissions=False,
		ignore_user_permissions=False,
		user=frappe.session.user,
		**kwargs,
	)


def _permissioned_get_value(doctype, filters=None, fieldname="name", *, as_dict=False):
	if isinstance(filters, str):
		filters = {"name": filters}
	fieldnames = fieldname if isinstance(fieldname, (list, tuple)) else [fieldname]
	if frappe.get_meta(doctype).issingle:
		# a Single has no table for get_list
		row = frappe._dict({f: _permissioned_get_single_value(doctype, f) for f in fieldnames})
	elif rows := _permissioned_get_list(doctype, filters=filters, fields=list(fieldnames), limit=1):
		row = rows[0]
	else:
		return None
	if as_dict:
		return row
	if isinstance(fieldname, (list, tuple)):
		return [row.get(f) for f in fieldname]
	return row.get(fieldname)


def _permissioned_get_single_value(doctype: str, fieldname: str):
	if not frappe.has_permission(doctype, "read"):
		raise frappe.PermissionError(_("No permission to read {0}").format(doctype))
	return frappe.db.get_single_value(doctype, fieldname)


def _permissioned_exists(doctype, filters=None) -> bool:
	if isinstance(filters, str):
		filters = {"name": filters}
	return bool(_permissioned_get_list(doctype, filters=filters, fields=["name"], limit=1))


def _permissioned_count(doctype, filters=None) -> int:
	rows = _permissioned_get_list(doctype, filters=filters, fields=[{"COUNT": "*", "as": "total"}])
	return rows[0].get("total") if rows else 0


_SKIP_BUILTINS = frozenset(
	{
		"execute",
		"grep",
		"read",
		"subagent",
		"web_fetch",
		"web_search",
		"search_knowledge",
		"search_attachments",
		"read_attachment",
		"update_memory",
		"load_skill",
		"request_secret",
	}
)


def _flow_builtins(tool_context: ToolContext | None = None) -> dict[str, Any]:
	"""The permission-checked builtins, callable as plain functions inside the sandbox.
	`execute` and the bound tools are left out. `ctx` is held in a closure, never a `partial`
	keyword or arg, so the sandbox can neither override it nor read it back off the function."""
	from frappe.flow.tools.builtins import BUILTIN_TOOLS

	def bind(func):
		def call(*args, **kwargs):
			kwargs.pop("ctx", None)
			return func(*args, ctx=tool_context, **kwargs)

		return call

	out = {t.name: bind(t.func) for t in BUILTIN_TOOLS if t.name not in _SKIP_BUILTINS}
	# the code's own transaction holds its calls, read-only or approved
	out["run_action"] = bind(_sandbox_run_action)
	out["call_api"] = bind(_sandbox_call_api)
	return out


class NeedsApproval(Exception):
	"""Read-only code tried to reach outside the database."""


def _stop(what: str, ctx: ToolContext | None, *args: Any, **kwargs: Any) -> NoReturn:
	stop = NeedsApproval(_("{0} can't run in read-only code.").format(what))
	# the code may catch the exception
	if ctx is not None:
		ctx.failure = stop
	raise stop


def _sandbox_run_action(doctype: str, names: list[str], action: str, args=None, *, ctx: ToolContext | None):
	from frappe.flow.tools.builtins import _run_action, function_title, is_function_path, is_read_function

	if ctx is not None and ctx.read_only and not is_read_function(action):
		_stop(function_title(action) if is_function_path(action) else action, ctx)
	return _run_action(doctype, names, action, args, ctx=ctx)


def _sandbox_call_api(
	method: str, args: dict[str, Any] | None = None, *, ctx: ToolContext | None
) -> dict[str, Any]:
	from frappe.flow.tools.builtins import _call_api, function_title, is_read_function

	if ctx is not None and ctx.read_only and not is_read_function(method):
		_stop(function_title(method), ctx)
	return _call_api(method, args, ctx=ctx)


def _call_read_function(ctx: ToolContext, function: str, **kwargs: Any) -> Any:
	from frappe.flow.tools.builtins import is_read_function

	if not is_read_function(function):
		_stop(function, ctx)
	return call_whitelisted_function(function, **kwargs)


def get_flow_safe_globals(*, tool_context: ToolContext | None = None) -> NamespaceDict:
	"""Code that runs as `read_only` (`tool_context.read_only`) gets a stop instead of what reaches
	outside the database: jobs, email, and functions not marked read-only."""
	user = frappe.session.user
	read_only = tool_context is not None and tool_context.read_only

	out = NamespaceDict(
		json=NamespaceDict(loads=json.loads, dumps=json.dumps),
		orjson=SAFE_ORJSON,
		as_json=frappe.as_json,
		dict=dict,
		_dict=frappe._dict,
		log=frappe.log,
		_=frappe._,
		scrub=frappe.scrub,
		html2text=html2text,
		guess_mimetype=mimetypes.guess_type,
		frappe=NamespaceDict(
			call=(lambda function, **kwargs: _call_read_function(tool_context, function, **kwargs))
			if read_only
			else call_whitelisted_function,
			enqueue=(lambda *a, **k: _stop("frappe.enqueue", tool_context)) if read_only else _gated_enqueue,
			is_job_queued=is_job_queued,
			user=user,
			session=frappe._dict(user=user),
			get_doc=_gated_get_doc,
			get_last_doc=_gated_get_last_doc,
			get_meta=_gated_get_meta,
			get_list=_permissioned_get_list,
			get_print=_gated_get_print,
			attach_print=_gated_attach_print,
			sendmail=(lambda *a, **k: _stop("frappe.sendmail", tool_context))
			if read_only
			else _gated_sendmail,
			log=frappe.log,
			log_error=safer_log_error,
			msgprint=frappe.msgprint,
			throw=frappe.throw,
			errprint=frappe.errprint,
			bold=frappe.bold,
			sanitize_html=frappe.utils.sanitize_html,
			get_fullname=frappe.utils.get_fullname,
			format=frappe.format_value,
			format_value=frappe.format_value,
			utils=NamespaceDict(**SAFE_DATA_UTILS),
			db=NamespaceDict(
				get_list=_permissioned_get_list,
				get_value=_permissioned_get_value,
				get_single_value=_permissioned_get_single_value,
				exists=_permissioned_exists,
				count=_permissioned_count,
			),
		),
	)

	out.frappe.update(SAFE_EXCEPTIONS)
	out.update(_flow_builtins(tool_context))

	out.update(safe_globals)
	out._write_ = _write
	out._getitem_ = _getitem
	out._getattr_ = _getattr_for_safe_exec
	out._print_ = FrappePrintCollector
	out._getiter_ = iter
	out._iter_unpack_sequence_ = RestrictedPython.Guards.guarded_iter_unpack_sequence
	out._inplacevar_ = protected_inplacevar
	out.update(get_python_builtins())

	return out
