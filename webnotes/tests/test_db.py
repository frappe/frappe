# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import webnotes
from webnotes.test_runner import make_test_records

class TestDB(unittest.TestCase):
	def test_get_value(self):
		webnotes.conn.sql("""delete from `tabProfile` where name not in ('Administrator', 'Guest')""")
		
		make_test_records("Profile")
		
		self.assertEquals(webnotes.conn.get_value("Profile", {"name": ["=", "Administrator"]}), "Administrator")
		self.assertEquals(webnotes.conn.get_value("Profile", {"name": ["like", "Admin%"]}), "Administrator")
		self.assertEquals(webnotes.conn.get_value("Profile", {"name": ["!=", "Guest"]}), "Administrator")
		
		from webnotes.utils import nowdate
		self.assertEquals(webnotes.conn.get_value("Profile", {"modified": ["<", nowdate()]}), "Administrator")
		self.assertEquals(webnotes.conn.get_value("Profile", {"modified": ["<=", nowdate()]}), "Administrator")
		self.assertEquals(webnotes.conn.get_value("Profile", {"modified": [">", nowdate()]}), "test1@example.com")
		self.assertEquals(webnotes.conn.get_value("Profile", {"modified": [">=", nowdate()]}), "test1@example.com")
		
		