# Copyright (c) 2020, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def execute():
	nts.reload_doc("core", "doctype", "DocField")

	if nts.db.has_column("DocField", "show_days"):
		nts.db.sql(
			"""
			UPDATE
				tabDocField
			SET
				hide_days = 1 WHERE show_days = 0
		"""
		)
		nts.db.sql_ddl("alter table tabDocField drop column show_days")

	if nts.db.has_column("DocField", "show_seconds"):
		nts.db.sql(
			"""
			UPDATE
				tabDocField
			SET
				hide_seconds = 1 WHERE show_seconds = 0
		"""
		)
		nts.db.sql_ddl("alter table tabDocField drop column show_seconds")

	nts.clear_cache(doctype="DocField")
