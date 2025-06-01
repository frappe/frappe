# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import nts
from nts.tests.utils import ntsTestCase

test_records = nts.get_test_records("Page")


class TestPage(ntsTestCase):
	def test_naming(self):
		self.assertRaises(
			nts.NameError,
			nts.get_doc(dict(doctype="Page", page_name="DocType", module="Core")).insert,
		)
