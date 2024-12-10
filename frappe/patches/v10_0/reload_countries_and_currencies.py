"""
Run this after updating country_info.json and or
"""
<<<<<<< HEAD
=======

>>>>>>> beab110ce9 (fix: clarify error message for child tables)
from frappe.utils.install import import_country_and_currency


def execute():
	import_country_and_currency()
