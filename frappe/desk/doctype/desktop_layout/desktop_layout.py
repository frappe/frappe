# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document


class DesktopLayout(Document):
	_DOCTYPE_NAME = "Desktop Layout"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		layout: DF.Code | None
		user: DF.Link | None
	# end: auto-generated types

	pass
