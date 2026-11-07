import pytz

from frappe.geo.country_info import get_all
from frappe.tests import UnitTestCase


class TestCountryInfo(UnitTestCase):
	def test_country_timezones_are_not_deprecated_aliases(self):
		for country, info in get_all().items():
			for timezone in info.get("timezones", []):
				self.assertIn(timezone, pytz.common_timezones, country)
