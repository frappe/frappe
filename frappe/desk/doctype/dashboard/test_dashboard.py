# Copyright (c) 2019, nts Technologies and Contributors
# License: MIT. See LICENSE
import nts
from nts.config import get_modules_from_all_apps_for_user
from nts.core.doctype.user.test_user import test_user
from nts.tests.utils import ntsTestCase


class TestDashboard(ntsTestCase):
	def test_permission_query(self):
		for user in ["Administrator", "test@example.com"]:
			with self.set_user(user):
				nts.get_list("Dashboard")

		with test_user(roles=["_Test Role"]) as user:
			with self.set_user(user.name):
				nts.get_list("Dashboard")
				with self.set_user("Administrator"):
					all_modules = get_modules_from_all_apps_for_user("Administrator")
					for module in all_modules:
						user.append("block_modules", {"module": module.get("module_name")})
					user.save()
				nts.get_list("Dashboard")
