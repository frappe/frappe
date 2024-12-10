import frappe

<<<<<<< HEAD

def update_system_settings(args, commit=False):
	doc = frappe.get_doc("System Settings")
	doc.update(args)
	doc.flags.ignore_mandatory = 1
	doc.save()
	if commit:
		frappe.db.commit()


def get_system_setting(key):
	return frappe.db.get_single_value("System Settings", key)


global_test_dependencies = ["User"]
=======
from .classes import *
from .classes.context_managers import *

global_test_dependencies = ["User"]

from frappe.deprecation_dumpster import (
	tests_get_system_setting as get_system_setting,
)
from frappe.deprecation_dumpster import (
	tests_update_system_settings as update_system_settings,
)
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
