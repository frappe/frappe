# Copyright (c) 2020, nts Technologies and Contributors
# License: MIT. See LICENSE

import nts
from nts.core.doctype.installed_applications.installed_applications import (
	InvalidAppOrder,
	update_installed_apps_order,
)
from nts.tests.utils import ntsTestCase


class TestInstalledApplications(ntsTestCase):
	def test_order_change(self):
		update_installed_apps_order(["nts"])
		self.assertRaises(InvalidAppOrder, update_installed_apps_order, [])
		self.assertRaises(InvalidAppOrder, update_installed_apps_order, ["nts", "deepmind"])
