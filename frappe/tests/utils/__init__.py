import logging

import frappe
from frappe.model.base_document import get_controller

logger = logging.Logger(__file__)

from .generators import *


def check_orpahned_doctypes():
	"""Check that all doctypes in DB actually exist after patch test"""

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


# TODO: move to dumpster (backwars compat) - not meant to be a public interface anymore
from frappe.tests.classes import IntegrationTestCase, MockedRequestTestCase, UnitTestCase
from frappe.tests.classes.context_managers import debug_on, timeout

# TODO: move to dumpster
FrappeTestCase = IntegrationTestCase
change_settings = IntegrationTestCase.change_settings
patch_hooks = UnitTestCase.patch_hooks
