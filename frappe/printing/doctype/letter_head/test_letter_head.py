# Copyright (c) 2017, nts Technologies and Contributors
# License: MIT. See LICENSE
import nts
from nts.tests.utils import ntsTestCase


class TestLetterHead(ntsTestCase):
	def test_auto_image(self):
		letter_head = nts.get_doc(
			dict(doctype="Letter Head", letter_head_name="Test", source="Image", image="/public/test.png")
		).insert()

		# test if image is automatically set
		self.assertTrue(letter_head.image in letter_head.content)
