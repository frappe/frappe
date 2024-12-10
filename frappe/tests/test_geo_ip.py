# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestGeoIP(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase


class TestGeoIP(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	def test_geo_ip(self):
		return
		from frappe.sessions import get_geo_ip_country

		self.assertEqual(get_geo_ip_country("223.29.223.255"), "India")
		self.assertEqual(get_geo_ip_country("4.18.32.80"), "United States")
		self.assertEqual(get_geo_ip_country("217.194.147.25"), "United States")
