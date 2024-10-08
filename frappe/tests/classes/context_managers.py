import logging
from contextlib import contextmanager
from functools import wraps
from inspect import isfunction, ismethod
from typing import Any

import frappe

from .integration_test_case import IntegrationTestCase
from .unit_test_case import UnitTestCase

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
	import pytz
	from freezegun import freeze_time as freezegun_freeze_time

	from frappe.utils.data import get_datetime, get_system_timezone

	if not is_utc:
		# Freeze time expects UTC or tzaware objects. We have neither, so convert to UTC.
		timezone = pytz.timezone(get_system_timezone())
		time_to_freeze = timezone.localize(get_datetime(time_to_freeze)).astimezone(pytz.utc)

	with freezegun_freeze_time(time_to_freeze, *args, **kwargs):
		yield


@UnitTestCase.registerAs(staticmethod)
@contextmanager
def set_user(user: str) -> None:
	"""Temporarily: set the user."""
	old_user = frappe.session.user
	frappe.set_user(user)
	yield
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
	# singles are cached by default, clear to avoid flake
	frappe.db.value_cache[settings] = {}
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


# NOTE: declare those who should also be made available directly frappe.tests.* namespace
# these can be general purpose context managers who do NOT depend on a particular
# test class setup, such as for example the IntegrationTestCase's connection to site
__all__ = [
	"freeze_time",
	"set_user",
	"patch_hooks",
	"change_settings",
	"switch_site",
	"enable_safe_exec",
	"debug_on",
	"timeout_context",
	"timeout",
]
