# Copyright (c) 2022, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import nts
from nts.config import get_modules_from_all_apps_for_user
from nts.tests.utils import ntsTestCase


class TestConfig(ntsTestCase):
	def test_get_modules(self):
		nts_modules = nts.get_all("Module Def", filters={"app_name": "nts"}, pluck="name")
		all_modules_data = get_modules_from_all_apps_for_user()
		all_modules = [x["module_name"] for x in all_modules_data]
		self.assertIsInstance(all_modules_data, list)
		self.assertFalse([x for x in nts_modules if x not in all_modules])
