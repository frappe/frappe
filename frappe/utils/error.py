# Copyright (c) 2015, Maxwell Morais and contributors
# License: MIT. See LICENSE

import functools
import inspect
import re
from collections import Counter
from contextlib import suppress

import frappe
from frappe.monitor import add_data_to_monitor

EXCLUDE_EXCEPTIONS = (
	frappe.AuthenticationError,
	frappe.CSRFTokenError,  # CSRF covers OAuth too
	frappe.SecurityException,
	frappe.InReadOnlyMode,
)

LDAP_BASE_EXCEPTION = "LDAPException"


def _is_ldap_exception(e):
	"""Check if exception is from LDAP library.

	This is a hack but ensures that LDAP is not imported unless it's required. This is tested in
	unittests in case the exception changes in future.
	"""

	for t in type(e).__mro__:
		if t.__name__ == LDAP_BASE_EXCEPTION:
			return True

	return False


def log_error(title=None, message=None, reference_doctype=None, reference_name=None, *, defer_insert=False):
	"""Log error to Error Log"""
	from frappe.monitor import get_trace_id
	from frappe.utils.sentry import capture_exception

	# Parameter ALERT:
	# the title and message may be swapped
	# the better API for this is log_error(title, message), and used in many cases this way
	# this hack tries to be smart about whats a title (single line ;-)) and fixes it

	traceback = None
	if message:
		if "\n" in title:  # traceback sent as title
			traceback, title = title, message
		else:
			traceback = message

	title = title or "Error"
	traceback = frappe.as_unicode(traceback or frappe.get_traceback(with_context=True))

	if not frappe.db:
		print(f"Failed to log error in db: {title}")
		return

	trace_id = get_trace_id()
	error_log = frappe.get_doc(
		doctype="Error Log",
		error=traceback,
		method=title,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		trace_id=trace_id,
	)

	# Capture exception data if telemetry is enabled
	capture_exception(message=f"{title}\n{traceback}")

	if frappe.flags.read_only or defer_insert:
		error_log.deferred_insert()
	else:
		return error_log.insert(ignore_permissions=True)


def log_error_snapshot(exception: Exception):
	if isinstance(exception, EXCLUDE_EXCEPTIONS) or _is_ldap_exception(exception):
		return

	logger = frappe.logger(with_more_info=True)

	try:
		log_error(title=str(exception), defer_insert=True)
		logger.error("New Exception collected in error log")
		add_data_to_monitor(exception=exception.__class__.__name__)
	except Exception as e:
		logger.error(f"Could not take error snapshot: {e}", exc_info=True)


def get_default_args(func):
	"""Get default arguments of a function from its signature."""
	signature = inspect.signature(func)
	return {k: v.default for k, v in signature.parameters.items() if v.default is not inspect.Parameter.empty}


def raise_error_on_no_output(error_message, error_type=None, keep_quiet=None):
	"""Decorate any function to throw error incase of missing output.

	:param error_message: error message to raise
	:param error_type: type of error to raise
	:param keep_quiet: control error raising with external factor.
	:type error_message: str
	:type error_type: Exception Class
	:type keep_quiet: function

	---
	Example:

	```py
	@raise_error_on_no_output("Ingredients are missing")
	def get_ingredients(_raise_error=1):
	    return


	# this will raise an Exception with message "Ingredients are missing"
	ingredients = get_ingredients()
	```

	---

	TODO: Remove keep_quiet flag after testing and fixing sendmail flow.
	"""

	def decorator_raise_error_on_no_output(func):
		@functools.wraps(func)
		def wrapper_raise_error_on_no_output(*args, **kwargs):
			response = func(*args, **kwargs)
			if callable(keep_quiet) and keep_quiet():
				return response

			default_kwargs = get_default_args(func)
			default_raise_error = default_kwargs.get("_raise_error")
			raise_error = kwargs.get("_raise_error") if "_raise_error" in kwargs else default_raise_error

			if (not response) and raise_error:
				frappe.throw(error_message, error_type or Exception)
			return response

		return wrapper_raise_error_on_no_output

	return decorator_raise_error_on_no_output


def guess_exception_source(exception: str) -> str | None:
	"""Attempts to guess source of error based on traceback.

	E.g.

	- For unhandled exception last python file from apps folder is responsible.
	- For frappe.throws the exception source is possibly present after skipping frappe.throw frames
	- For server script the file name contains SERVER_SCRIPT_FILE_PREFIX

	"""
	from frappe.utils.safe_exec import SERVER_SCRIPT_FILE_PREFIX

	with suppress(Exception):
		installed_apps = frappe.get_installed_apps()
		app_priority = {app: installed_apps.index(app) for app in installed_apps}

		APP_NAME_REGEX = re.compile(r".*File.*apps/(?P<app_name>\w+)/\1/")

		apps = Counter()
		for line in reversed(exception.splitlines()):
			if SERVER_SCRIPT_FILE_PREFIX in line:
				return "Server Script"

			if matches := APP_NAME_REGEX.match(line):
				app_name = matches.group("app_name")
				apps[app_name] += app_priority.get(app_name, 0)

		if (probably_source := apps.most_common(1)) and probably_source[0][0] != "frappe":
			return f"{probably_source[0][0]} (app)"
