import functools
import sys
from typing import Literal

import frappe
from frappe import _
from frappe.utils import strip_html_tags
from frappe.utils.data import safe_decode

_strip_html_tags = functools.lru_cache(maxsize=1024)(strip_html_tags)


def msgprint(
	msg: str,
	title: str | None = None,
	raise_exception: bool | type[Exception] | Exception = False,
	as_table: bool = False,
	as_list: bool = False,
	indicator: Literal["blue", "green", "orange", "red", "yellow"] | None = None,
	alert: bool = False,
	primary_action: dict | None = None,
	is_minimizable: bool = False,
	wide: bool = False,
	*,
	realtime=False,
) -> None:
	"""Print a message to the user (via HTTP response).
	Messages are sent in the `__server_messages` property in the
	response JSON and shown in a pop-up / modal.

	:param msg: Message.
	:param title: [optional] Message title. Default: "Message".
	:param raise_exception: [optional] Raise given exception and show message.
	:param as_table: [optional] If `msg` is a list of lists, render as HTML table.
	:param as_list: [optional] If `msg` is a list, render as un-ordered list.
	:param primary_action: [optional] Bind a primary server/client side action.
	:param is_minimizable: [optional] Allow users to minimize the modal
	:param wide: [optional] Show wide modal
	:param realtime: Publish message immediately using websocket.
	"""
	import inspect

	msg = safe_decode(msg)
	out = frappe._dict(message=msg)

	def _raise_exception():
		if raise_exception:
			if inspect.isclass(raise_exception) and issubclass(raise_exception, Exception):
				exc = raise_exception(msg)
			elif isinstance(raise_exception, Exception):
				exc = raise_exception
				exc.args = (msg,)
			else:
				exc = frappe.ValidationError(msg)
			if out.__frappe_exc_id:
				exc.__frappe_exc_id = out.__frappe_exc_id
			raise exc

	if frappe.flags.mute_messages:
		_raise_exception()
		return

	if as_table and type(msg) in (list, tuple):
		out.as_table = 1

	if as_list and type(msg) in (list, tuple):
		out.as_list = 1

	if sys.stdin and sys.stdin.isatty():
		if out.as_list:
			msg = [_strip_html_tags(msg) for msg in out.message]
		else:
			msg = _strip_html_tags(out.message)

	if frappe.flags.print_messages and out.message:
		print(f"Message: {_strip_html_tags(out.message)}")

	out.title = title or _("Message", context="Default title of the message dialog")

	if not indicator and raise_exception:
		indicator = "red"

	if indicator:
		out.indicator = indicator

	if is_minimizable:
		out.is_minimizable = is_minimizable

	if alert:
		out.alert = 1

	if raise_exception:
		out.raise_exception = 1
		out.__frappe_exc_id = frappe.generate_hash()

	if primary_action:
		out.primary_action = primary_action

	if wide:
		out.wide = wide

	if realtime:
		frappe.publish_realtime(event="msgprint", message=out)
	else:
		frappe.message_log.append(out)
	_raise_exception()


def toast(message: str, indicator: Literal["blue", "green", "orange", "red", "yellow"] | None = None):
	msgprint(message, indicator=indicator, alert=True)


def clear_messages():
	frappe.local.message_log = []


def get_message_log() -> list[dict]:
	return [msg_out for msg_out in frappe.local.message_log]


def clear_last_message():
	if len(frappe.local.message_log) > 0:
		frappe.local.message_log = frappe.local.message_log[:-1]


def throw(
	msg: str,
	exc: type[Exception] | Exception = frappe.ValidationError,
	title: str | None = None,
	is_minimizable: bool = False,
	wide: bool = False,
	as_list: bool = False,
	primary_action=None,
) -> None:
	"""Throw execption and show message (`msgprint`).

	:param msg: Message.
	:param exc: Exception class. Default `frappe.ValidationError`
	:param title: [optional] Message title. Default: "Message".
	:param is_minimizable: [optional] Allow users to minimize the modal
	:param wide: [optional] Show wide modal
	:param as_list: [optional] If `msg` is a list, render as un-ordered list.
	:param primary_action: [optional] Bind a primary server/client side action.
	"""
	msgprint(
		msg,
		raise_exception=exc,
		title=title,
		indicator="red",
		is_minimizable=is_minimizable,
		wide=wide,
		as_list=as_list,
		primary_action=primary_action,
	)


def throw_permission_error():
	throw(_("Not permitted"), frappe.PermissionError)


__all__ = [
	"clear_last_message",
	"clear_messages",
	"get_message_log",
	"msgprint",
	"throw",
	"throw_permission_error",
	"toast",
]
