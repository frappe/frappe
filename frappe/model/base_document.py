# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Kept for backward compatibility. Everything here now lives in `frappe.model.document`."""

from frappe.model.document import *

# pickles of extended doctypes made before the merge reference this path
from frappe.model.document import _reconstruct_extended_instance
