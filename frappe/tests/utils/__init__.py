import logging
import os
import time
from functools import wraps

import frappe

logger = logging.Logger(__file__)

from .generators import *


def whitelist_for_tests(**whitelist_kwargs):
	"""Decorator to whitelist test endpoints.

	Only allows access when running in test mode or running a development server with testing enabled.
	Supports all parameters that @frappe.whitelist() accepts.

	Usage:
		@whitelist_for_tests(allow_guest=True)
		def my_guest_test_endpoint():
			...
	"""

	def decorator(fn):
		@wraps(fn)
		def wrapper(*args, **kwargs):
			if not (
				frappe.in_test or (frappe._dev_server and frappe.conf.allow_tests) or os.environ.get("CI")
			):
				frappe.throw(  # nosemgrep: frappe-missing-translate-function-python
					'Test endpoints are only available when running in test mode or running a development server ("bench start") with the "allow_tests" site config enabled'
				)
			return fn(*args, **kwargs)

		return frappe.whitelist(**whitelist_kwargs)(wrapper)

	return decorator


def check_orpahned_doctypes():
	"""Check that all doctypes in DB actually exist after patch test"""
	from frappe.model.base_document import get_controller

	doctypes = frappe.get_all("DocType", {"custom": 0}, pluck="name")
	orpahned_doctypes = []

	for doctype in doctypes:
		try:
			get_controller(doctype)
		except ImportError:
			orpahned_doctypes.append(doctype)

	if orpahned_doctypes:
		frappe.throw(
			"Following doctypes exist in DB without controller.\n {}".format("\n".join(orpahned_doctypes))
		)


def toggle_test_mode(enable: bool):
	"""Enable or disable `frappe.in_test` (and related deprecated flag)"""
	frappe.in_test = enable
	frappe.local.flags.in_test = enable


def wait_for_job(job_id: str, wait_timeout: float = 10):
	"""Wait for an enqueued job to stop running, so a test does not race the worker.

	A worker holds a row lock on everything it touches, and frappe asks for those locks with
	NOWAIT, so a test that writes the same rows fails instead of queueing. Returns quietly after
	`wait_timeout` seconds if the job never runs, e.g. when no worker is up.
	"""
	from frappe.utils.background_jobs import is_job_enqueued

	# job_id may be "site||abc123"; is_job_enqueued wants just "abc123"
	job_id = job_id.split("||", 1)[-1]

	deadline = time.monotonic() + wait_timeout

	while time.monotonic() < deadline:
		if not is_job_enqueued(job_id):
			return
		time.sleep(0.2)


from frappe.deprecation_dumpster import (
	get_tests_CompatFrappeTestCase,
)
from frappe.deprecation_dumpster import (
	tests_change_settings as change_settings,
)
from frappe.deprecation_dumpster import (
	tests_debug_on as debug_on,
)

FrappeTestCase = get_tests_CompatFrappeTestCase()

from frappe.deprecation_dumpster import (
	tests_patch_hooks as patch_hooks,
)
from frappe.deprecation_dumpster import (
	tests_timeout as timeout,
)
from frappe.deprecation_dumpster import (
	tests_utils_get_dependencies as get_dependencies,
)
