import nts
from nts import format
from nts.tests.utils import ntsTestCase


class TestFormatter(ntsTestCase):
	def test_currency_formatting(self):
		df = nts._dict({"fieldname": "amount", "fieldtype": "Currency", "options": "currency"})

		doc = nts._dict({"amount": 5})
		nts.db.set_default("currency", "INR")

		# if currency field is not passed then default currency should be used.
		self.assertEqual(format(100000, df, doc, format="#,###.##"), "₹ 100,000.00")

		doc.currency = "USD"
		self.assertEqual(format(100000, df, doc, format="#,###.##"), "$ 100,000.00")

		nts.db.set_default("currency", None)
