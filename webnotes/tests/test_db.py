# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

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
		
		