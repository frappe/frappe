# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""A permission-respecting sandbox for Flow's `execute` tool.

Reuses frappe's RestrictedPython machinery (compilation, guards, flags) but exposes
an allowlisted namespace where every data function enforces the current user's
permissions. Functions that bypass permissions — raw SQL, the query builder,
`db.set_value`, `get_all` — are left out entirely.
"""

from __future__ import annotations

import json
import mimetypes
from typing import Any

import frappe
import RestrictedPython.Guards
from frappe import _
from frappe.core.utils import html2text
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
from RestrictedPython import safe_globals


def safe_exec(
	script: str,
	_globals: dict | None = None,
	_locals: dict | None = None,
	*,
	script_filename: str | None = None,
):
	exec_globals = get_flow_safe_globals()
	if _globals:
		exec_globals.update(_globals)

	filename = SERVER_SCRIPT_FILE_PREFIX
	if script_filename:
		filename += f": {frappe.scrub(script_filename)}"

	with safe_exec_flags():
		exec(_compile_code(script, filename=filename), exec_globals, _locals)

	return exec_globals, _locals


def _gated_get_doc(*args: Any, **kwargs: Any) -> dict:
	doc = frappe.get_doc(*args, **kwargs)
	doc.check_permission("read")
	return doc.as_dict()


def _gated_get_last_doc(*args: Any, **kwargs: Any) -> dict:
	doc = frappe.get_last_doc(*args, **kwargs)
	doc.check_permission("read")
	return doc.as_dict()


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
	rows = _permissioned_get_list(doctype, filters=filters, fields=list(fieldnames), limit=1)
	if not rows:
		return None
	row = rows[0]
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


_SKIP_BUILTINS = frozenset({"execute", "search_knowledge"})


def _flow_builtins() -> dict[str, Any]:
	"""The permission-checked builtins, callable as plain functions inside the sandbox.
	`execute` (no recursion) and `search_knowledge` (needs a bound scope) are left out."""
	from flow.tools.builtins import BUILTIN_TOOLS

	return {t.name: t.func for t in BUILTIN_TOOLS if t.name not in _SKIP_BUILTINS}


def get_flow_safe_globals() -> NamespaceDict:
	user = frappe.session.user

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
			call=call_whitelisted_function,
			enqueue=safe_enqueue,
			is_job_queued=is_job_queued,
			user=user,
			session=frappe._dict(user=user),
			get_doc=_gated_get_doc,
			get_last_doc=_gated_get_last_doc,
			get_meta=_gated_get_meta,
			get_list=_permissioned_get_list,
			get_print=_gated_get_print,
			attach_print=_gated_attach_print,
			sendmail=frappe.sendmail,
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
	out.update(_flow_builtins())

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
