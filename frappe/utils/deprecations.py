"""Utils for deprecating functionality in Framework.

WARNING: This file is internal, instead of depending just copy the code or use deprecation
libraries.
"""

from frappe.deprecation_dumpster import (
	_old_deprecated as deprecated,
)
from frappe.deprecation_dumpster import (
	_old_deprecation_warning as deprecation_warning,
)
