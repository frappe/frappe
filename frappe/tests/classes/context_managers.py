import logging
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import TYPE_CHECKING, Any

import frappe

from .integration_test_case import IntegrationTestCase
from .unit_test_case import UnitTestCase

if TYPE_CHECKING:
	from frappe.model import Document

# NOTE: please lazily import any further namespaces within the contextmanager below

logger = logging.Logger(__file__)

###############################################################
# Decorators and Context Managers Implementation
# (each cm is automatically a decorator)
# NOTE: Keep all imports local to the decorator (!)
###############################################################


@UnitTestCase.registerAs(staticmethod)
@contextmanager
def freeze_time(time_to_freeze: Any, is_utc: bool = False, *args: Any, **kwargs: Any) -> None:
	"""Temporarily: freeze time with freezegun."""
	from datetime import UTC
	from zoneinfo import ZoneInfo

	from freezegun import freeze_time as freezegun_freeze_time

	from frappe.utils.data import get_datetime, get_system_timezone

	if not is_utc:
		# Freeze time expects UTC or tzaware objects. We have neither, so convert to UTC.
		time_to_freeze = (
			get_datetime(time_to_freeze).replace(tzinfo=ZoneInfo(get_system_timezone())).astimezone(UTC)
		)

	with freezegun_freeze_time(time_to_freeze, *args, **kwargs):
		yield


@UnitTestCase.registerAs(staticmethod)
@contextmanager
def set_user(user: str):
	"""Temporarily: set the user."""
	try:
		old_user = frappe.session.user
		frappe.set_user(user)
		yield
	finally:
		frappe.set_user(old_user)


@UnitTestCase.registerAs(staticmethod)
@contextmanager
def patch_hooks(overridden_hooks: dict) -> None:
	"""Temporarily: patch a hook."""
	from unittest.mock import patch

	get_hooks = frappe.get_hooks

	def patched_hooks(hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
		if hook in overridden_hooks:
			return overridden_hooks[hook]
		return get_hooks(hook, default, app_name)

	with patch.object(frappe, "get_hooks", patched_hooks):
		yield


@IntegrationTestCase.registerAs(staticmethod)
@contextmanager
def change_settings(doctype, settings_dict=None, /, commit=False, **settings) -> None:
	"""Temporarily: change settings in a settings doctype."""
	import copy

	if settings_dict is None:
		settings_dict = settings

	settings = frappe.get_doc(doctype)
	previous_settings = copy.deepcopy(settings_dict)
	for key in previous_settings:
		previous_settings[key] = getattr(settings, key)

	for key, value in settings_dict.items():
		setattr(settings, key, value)
	settings.save(ignore_permissions=True)
	if commit:
		frappe.db.commit()
	yield
	settings = frappe.get_doc(doctype)
	for key, value in previous_settings.items():
		setattr(settings, key, value)
	settings.save(ignore_permissions=True)
	if commit:
		frappe.db.commit()


@IntegrationTestCase.registerAs(staticmethod)
@contextmanager
def switch_site(site: str) -> None:
	"""Temporarily: drop current connection and switch to a different site."""
	old_site = frappe.local.site
	frappe.init(site, force=True)
	frappe.connect()
	yield
	frappe.destroy()
	frappe.init(old_site, force=True)
	frappe.connect()


@UnitTestCase.registerAs(staticmethod)
@contextmanager
def enable_safe_exec() -> None:
	"""Temporarily: enable safe exec (server scripts)."""
	import os

	from frappe.installer import update_site_config
	from frappe.utils.safe_exec import SAFE_EXEC_CONFIG_KEY

	conf = os.path.join(frappe.local.sites_path, "common_site_config.json")
	update_site_config(SAFE_EXEC_CONFIG_KEY, 1, validate=False, site_config_path=conf)
	yield
	update_site_config(SAFE_EXEC_CONFIG_KEY, 0, validate=False, site_config_path=conf)


@UnitTestCase.registerAs(staticmethod)
@contextmanager
def debug_on(*exceptions) -> None:
	"""Temporarily: enter an interactive debugger on specified exceptions, default: (AssertionError,)."""
	import pdb
	import sys
	import traceback

	if not exceptions:
		exceptions = (AssertionError,)

	try:
		yield
	except exceptions as e:
		exc_type, exc_value, exc_traceback = sys.exc_info()
		# Pretty print the exception
		print("\n\033[91m" + "=" * 60 + "\033[0m")  # Red line
		print("\033[93m" + str(exc_type.__name__) + ": " + str(exc_value) + "\033[0m")
		print("\033[91m" + "=" * 60 + "\033[0m")  # Red line

		# Print the formatted traceback
		traceback_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
		for line in traceback_lines:
			print("\033[96m" + line.rstrip() + "\033[0m")  # Cyan color

		print("\033[91m" + "=" * 60 + "\033[0m")  # Red line
		print("\033[92mEntering post-mortem debugging\033[0m")
		print("\033[91m" + "=" * 60 + "\033[0m")  # Red line
		pdb.post_mortem()

		raise e


@UnitTestCase.registerAs(staticmethod)
@contextmanager
def timeout_context(seconds=30, error_message="Operation timed out.") -> None:
	"""Temporarily: timeout an operation."""
	import signal

	def _handle_timeout(signum, frame):
		raise Exception(error_message)

	signal.signal(signal.SIGALRM, _handle_timeout)
	signal.alarm(30 if callable(seconds) else seconds)
	yield
	signal.alarm(0)


def timeout(seconds=30, error_message="Operation timed out."):
	"""Timeout decorator to ensure a test doesn't run for too long."""

	def decorator(func=None):
		@wraps(func)
		def wrapper(*args, **kwargs):
			with timeout_context(seconds, error_message):
				return func(*args, **kwargs)

		return wrapper

	# Support bare @timeout
	if callable(seconds):
		return decorator(seconds)
	return decorator


@UnitTestCase.registerAs(staticmethod)
@contextmanager
def trace_fields(
	doc_class: type,
	field_name: str | None = None,
	forbidden_values: list | None = None,
	custom_validation: Callable | None = None,
	**field_configs: dict[str, list | Callable | None],
) -> "Document":
	"""
	A context manager for temporarily tracing fields in a DocType.

	Can be used in two ways:
	1. Tracing a single field:
	   trace_fields(DocType, "field_name", forbidden_values=[...], custom_validation=...)
	2. Tracing multiple fields:
	   trace_fields(DocType, field1={"forbidden_values": [...], "custom_validation": ...}, ...)

	Args:
	    doc_class (Document): The DocType class to modify.
	    field_name (str, optional): The name of the field to trace (for single field tracing).
	    forbidden_values (list, optional): A list of forbidden values for the field (for single field tracing).
	    custom_validation (callable, optional): A custom validation function (for single field tracing).
	    **field_configs: Keyword arguments for multiple field tracing, where each key is a field name and
	                     the value is a dict containing 'forbidden_values' and/or 'custom_validation'.

	Yields:
	    Document class
	"""
	from frappe.model.trace import traced_field

	original_attrs = {}
	original_init = doc_class.__init__

	# Prepare configurations
	if field_name:
		field_configs = {
			field_name: {"forbidden_values": forbidden_values, "custom_validation": custom_validation}
		}

	# Apply traced fields
	for f_name, config in field_configs.items():
		original_attrs[f_name] = getattr(doc_class, f_name, None)
		f_forbidden_values = config.get("forbidden_values")
		f_custom_validation = config.get("custom_validation")
		setattr(doc_class, f_name, traced_field(f_name, f_forbidden_values, f_custom_validation))

	# Modify init method
	def new_init(self, *args, **kwargs):
		original_init(self, *args, **kwargs)
		for f_name in field_configs:
			setattr(self, f"_{f_name}", getattr(self, f_name, None))

	doc_class.__init__ = new_init

	yield doc_class

	# Restore original attributes and init method
	for f_name, original_attr in original_attrs.items():
		if original_attr is not None:
			setattr(doc_class, f_name, original_attr)
		else:
			delattr(doc_class, f_name)
	doc_class.__init__ = original_init


# NOTE: declare those who should also be made available directly frappe.tests.* namespace
# these can be general purpose context managers who do NOT depend on a particular
# test class setup, such as for example the IntegrationTestCase's connection to site
__all__ = [
	"change_settings",
	"debug_on",
	"enable_safe_exec",
	"freeze_time",
	"patch_hooks",
	"set_user",
	"switch_site",
	"timeout",
	"timeout_context",
	"trace_fields",
]
