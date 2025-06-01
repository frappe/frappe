# Copyright (c) 2015, nts Technologies and Contributors
# License: MIT. See LICENSE
import nts
from nts.contacts.doctype.address_template.address_template import get_default_address_template
from nts.tests.utils import ntsTestCase
from nts.utils.jinja import validate_template


class TestAddressTemplate(ntsTestCase):
	def setUp(self) -> None:
		nts.db.delete("Address Template", {"country": "India"})
		nts.db.delete("Address Template", {"country": "Brazil"})

	def test_default_address_template(self):
		validate_template(get_default_address_template())

	def test_default_is_unset(self):
		nts.get_doc({"doctype": "Address Template", "country": "India", "is_default": 1}).insert()

		self.assertEqual(nts.db.get_value("Address Template", "India", "is_default"), 1)

		nts.get_doc({"doctype": "Address Template", "country": "Brazil", "is_default": 1}).insert()

		self.assertEqual(nts.db.get_value("Address Template", "India", "is_default"), 0)
		self.assertEqual(nts.db.get_value("Address Template", "Brazil", "is_default"), 1)

	def test_delete_address_template(self):
		india = nts.get_doc({"doctype": "Address Template", "country": "India", "is_default": 0}).insert()

		brazil = nts.get_doc(
			{"doctype": "Address Template", "country": "Brazil", "is_default": 1}
		).insert()

		india.reload()  # might have been modified by the second template
		india.delete()  # should not raise an error

		self.assertRaises(nts.ValidationError, brazil.delete)
