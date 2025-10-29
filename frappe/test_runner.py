# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
DEPRECATED.

This entire file is deprecated and will be removed in v17.

DO NOT ADD ANYTHING!
"""

from frappe.deprecation_dumpster import (
	test_runner_add_to_test_record_log as add_to_test_record_log,
)
from frappe.deprecation_dumpster import (
	test_runner_get_dependencies as get_dependencies,
)
from frappe.deprecation_dumpster import (
	test_runner_get_modules as get_modules,
)
from frappe.deprecation_dumpster import (
	test_runner_get_test_record_log as get_test_record_log,
)
from frappe.deprecation_dumpster import (
	test_runner_main as main,
)
from frappe.deprecation_dumpster import (
	test_runner_make_test_objects as make_test_objects,
)
from frappe.deprecation_dumpster import (
	test_runner_make_test_records as make_test_records,
)
from frappe.deprecation_dumpster import (
	test_runner_make_test_records_for_doctype as make_test_records_for_doctype,
)
from frappe.deprecation_dumpster import (
	test_runner_print_mandatory_fields as print_mandatory_fields,
)
from frappe.deprecation_dumpster import (
	test_xmlrunner_wrapper as xml_runner_wrapper,
)
from frappe.testing.result import SLOW_TEST_THRESHOLD
