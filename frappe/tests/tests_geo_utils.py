# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import unittest

import frappe
from frappe.geo.utils import get_coords


class TestGeoUtils(unittest.TestCase):
	def setUp(self):
		self.todo = frappe.get_doc(
			dict(doctype='ToDo', description='Test description', assigned_by='Administrator')).insert()

		self.test_location_dict = {'type': 'FeatureCollection', 'features': [
			{'type': 'Feature', 'properties': {}, "geometry": {'type': 'Point', 'coordinates': [49.20433, 55.753395]}}]}
		self.test_location = frappe.get_doc({'name': 'Test Location', 'doctype': 'Location',
											 'location': str(self.test_location_dict)})

		self.test_filter_exists = [['Location', 'name', 'like', '%Test Location%']]
		self.test_filter_not_exists = [['Location', 'name', 'like', '%Test Location Not exists%']]
		self.test_filter_todo = [['ToDo', 'description', 'like', '%Test description%']]

	def test_get_coords_location_with_filter_exists(self):
		coords = get_coords('Location', self.test_filter_exists, 'location_field')
		self.assertEqual(self.test_location_dict['features'][0]['geometry'], coords['features'][0]['geometry'])

	def test_get_coords_location_with_filter_not_exists(self):
		coords = get_coords('Location', self.test_filter_not_exists, 'location_field')
		self.assertEqual(coords, {'type': 'FeatureCollection', 'features': []})

	def test_get_coords_from_not_existable_location(self):
		self.assertRaises(frappe.ValidationError, get_coords, 'ToDo', self.test_filter_todo, 'location_field')

	def test_get_coords_from_not_existable_coords(self):
		self.assertRaises(frappe.ValidationError, get_coords, 'ToDo', self.test_filter_todo, 'coordinates')

	def tearDown(self):
		self.todo.delete()
