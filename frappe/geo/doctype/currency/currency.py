# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document

DEFAULT_ENABLED_CURRENCIES = ("INR", "USD", "GBP", "EUR", "AED", "AUD", "JPY", "CNY", "CHF")


class Currency(Document):
	# NOTE: During installation country docs are bulk inserted.
	def validate(self):
		frappe.clear_cache()


def enable_default_currencies():
	frappe.db.set_value("Currency", {"name": ("in", DEFAULT_ENABLED_CURRENCIES)}, "enabled", 1)
