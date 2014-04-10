# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import unittest
from frappe.utils import filter_composed_values

class TestFalsy(unittest.TestCase):

	def test_dict(self):
		a = {
			'none': None,
			'not_none': 1
		}
		self.assertFalse('none' in filter_composed_values(a))

	def test_list(self):
		a = [None, False, 0, 1]
		self.assertEqual(len(filter_composed_values(a)), 1)
	
	def test_test_fn(self):
		a = [None, False, 0, 1]
		self.assertEqual(len(filter_composed_values(a, lambda x: x!= None)), 3)
	
	def test_composed(self):
		in_val = {
			'this is none': None,
			'this is not none': 1,
			'this is a list': [None, None, 2, 3],
			'this is a dict': {
				'a': None,
				'b': 4,
				'd': [ None, {'hello': 'world'}]
			}
		}
		
		out_val = {'this is a dict': {
			'b': 4, 
			'd': [{
				'hello': 'world'
			}]},
			'this is a list': [2, 3],
			'this is not none': 1
		}
		self.assertEqual(filter_composed_values(in_val), out_val)



