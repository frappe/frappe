# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# pre loaded

import nts
from nts.tests.utils import ntsTestCase


class TestUser(ntsTestCase):
	def test_default_currency_on_setup(self):
		usd = nts.get_doc("Currency", "USD")
		self.assertDocumentEqual({"enabled": 1, "fraction": "Cent"}, usd)
