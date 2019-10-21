from __future__ import unicode_literals
import unittest
from frappe.utils.safe_exec import safe_exec

class TestSafeExec(unittest.TestCase):
	def test_import_fails(self):
		self.assertRaises(ImportError, safe_exec, 'import os')

	def test_internal_attributes(self):
		self.assertRaises(SyntaxError, safe_exec, '().__class__.__call__')