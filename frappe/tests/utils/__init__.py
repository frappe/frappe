import logging

import frappe

logger = logging.Logger(__file__)

from .generators import *


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
