"""
Run this after updating country_info.json and or
"""
from nts.utils.install import import_country_and_currency


def execute():
	import_country_and_currency()
