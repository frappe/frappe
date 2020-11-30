# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest
from PIL import Image
from frappe.utils.image import strip_exif_data
import io

class TestImage(unittest.TestCase):
	def test_strip_exif_data(self):
		original_image = Image.open("../apps/frappe/frappe/tests/data/exif_sample_image.jpg")
		original_image_content = io.open("../apps/frappe/frappe/tests/data/exif_sample_image.jpg", mode='rb').read()

		new_image_content = strip_exif_data(original_image_content)
		new_image = Image.open(io.BytesIO(new_image_content))

		self.assertEqual(new_image._getexif(), None)
		self.assertNotEqual(original_image._getexif(), new_image._getexif())