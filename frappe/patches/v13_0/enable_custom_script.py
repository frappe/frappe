# Copyright (c) 2020, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def execute():
	"""Enable all the existing Client script"""

	nts.db.sql(
		"""
		UPDATE `tabClient Script` SET enabled=1
	"""
	)
