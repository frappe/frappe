# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest

class TestGeoIP(unittest.TestCase):
	def test_geo_ip(self):
		return
		from frappe.sessions import get_geo_ip_country
		self.assertEqual(get_geo_ip_country("223.29.223.255"), "India")
		self.assertEqual(get_geo_ip_country("4.18.32.80"), "United States")
		self.assertEqual(get_geo_ip_country("217.194.147.25"), "United States")