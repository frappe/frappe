# Copyright (c) 2024, nts Technologies and Contributors
# See license.txt

import nts
from nts.tests.utils import ntsTestCase


class TestSystemHealthReport(ntsTestCase):
	def test_it_works(self):
		nts.get_doc("System Health Report")
