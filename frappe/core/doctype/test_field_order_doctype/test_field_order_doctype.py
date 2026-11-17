# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class TestFieldOrderDocType(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		field_1: DF.Data | None
		field_2: DF.Data | None
		field_4: DF.Data | None
		field_5: DF.Data | None
	# end: auto-generated types

	_DOCTYPE_NAME = "Test Field Order DocType"
