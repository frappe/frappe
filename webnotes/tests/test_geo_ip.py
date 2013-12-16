# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import webnotes
import unittest

class TestGeoIP(unittest.TestCase):
	def test_geo_ip(self):
		return
		from webnotes.sessions import get_geo_ip_country
		self.assertEquals(get_geo_ip_country("223.29.223.255"), "India")
		self.assertEquals(get_geo_ip_country("4.18.32.80"), "United States")
		self.assertEquals(get_geo_ip_country("217.194.147.25"), "United States")