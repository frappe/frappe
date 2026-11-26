from pathlib import Path

import pytz

import frappe
from frappe.geo.country_info import get_all
from frappe.tests import UnitTestCase


class TestCountryInfo(UnitTestCase):
	def test_country_timezones_are_not_deprecated_aliases(self):
		for country, info in get_all().items():
			for timezone in info.get("timezones", []):
				self.assertIn(timezone, pytz.common_timezones, country)

	def test_country_flag_svg_exists_for_each_country_code(self):
		flags_dir = Path(frappe.get_app_path("frappe", "public", "images", "flags"))
		for country, info in get_all().items():
			with self.subTest(country=country):
				flag_path = flags_dir / f"{info['code']}.svg"
				self.assertTrue(flag_path.is_file(), msg=str(flag_path))
