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


from frappe.deprecation_dumpster import (
	get_tests_FrappeTestCase,
	get_tests_IntegrationTestCase,
	get_tests_UnitTestCase,
)
from frappe.deprecation_dumpster import (
	tests_change_settings as change_settings,
)
from frappe.deprecation_dumpster import (
	tests_debug_on as debug_on,
)

FrappeTestCase = get_tests_FrappeTestCase()
IntegrationTestCase = get_tests_IntegrationTestCase()
UnitTestCase = get_tests_UnitTestCase()

from frappe.deprecation_dumpster import (
	tests_patch_hooks as patch_hooks,
)
from frappe.deprecation_dumpster import (
	tests_timeout as timeout,
)
from frappe.deprecation_dumpster import (
	tests_utils_get_dependencies as get_dependencies,
)
