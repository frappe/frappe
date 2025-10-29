import frappe

from .classes import *
from .classes.context_managers import *

global_test_dependencies = ["User"]

from frappe.deprecation_dumpster import (
	tests_get_system_setting as get_system_setting,
)
from frappe.deprecation_dumpster import (
	tests_update_system_settings as update_system_settings,
)
