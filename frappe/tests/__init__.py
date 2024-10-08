import frappe

from .classes import *
from .classes.context_managers import *

global_test_dependencies = ["User"]

# TODO: move to dumpster - not meant to be a public interface anymore
import frappe.tests.utils as utils

utils.IntegrationTestCase = IntegrationTestCase
utils.UnitTestCase = UnitTestCase
utils.FrappeTestCase = IntegrationTestCase
utils.change_settings = change_settings
utils.patch_hooks = patch_hooks
utils.debug_on = debug_on
utils.timeout = timeout


# TODO: move to dumpster
def update_system_settings(args, commit=False):
	doc = frappe.get_doc("System Settings")
	doc.update(args)
	doc.flags.ignore_mandatory = 1
	doc.save()
	if commit:
		frappe.db.commit()


# TODO: move to dumpster
def get_system_setting(key):
	return frappe.db.get_single_value("System Settings", key)
