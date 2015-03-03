# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import frappe, unittest

from frappe.desk.form.utils import get_linked_docs

class TestForm(unittest.TestCase):
	def test_linked_with(self):
		results = get_linked_docs("Role", "System Manager")
		self.assertTrue("User" in results)
		self.assertTrue("DocType" in results)
		
if __name__=="__main__":
	frappe.connect()
	unittest.main()
