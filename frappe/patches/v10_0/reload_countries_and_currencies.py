"""
Run this after updating country_info.json and or
"""
from frappe.utils.install import import_country_and_currency


def execute() -> None:
	import_country_and_currency()
