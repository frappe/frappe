# Copyright (c) 2020, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def execute():
	nts.reload_doc("email", "doctype", "Newsletter")
	nts.db.sql(
		"""
		UPDATE tabNewsletter
		SET content_type = 'Rich Text'
	"""
	)
