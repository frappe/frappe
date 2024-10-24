# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""docfield utililtes"""

import frappe


def supports_translation(fieldtype) -> bool:
	return fieldtype in ["Data", "Select", "Text", "Small Text", "Text Editor"]
