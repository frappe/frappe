# Copyright (c) 2022, nts Technologies and contributors
# For license information, please see license.txt


from nts.core.report.database_storage_usage_by_tables.database_storage_usage_by_tables import (
	execute,
)
from nts.tests.utils import ntsTestCase


class TestDBUsageReport(ntsTestCase):
	def test_basic_query(self):
		_, data = execute()
		tables = [d.table for d in data]
		self.assertFalse({"tabUser", "tabDocField"}.difference(tables))
