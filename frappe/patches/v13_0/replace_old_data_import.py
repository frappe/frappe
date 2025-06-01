# Copyright (c) 2020, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def execute():
	if not nts.db.table_exists("Data Import"):
		return

	meta = nts.get_meta("Data Import")
	# if Data Import is the new one, return early
	if meta.fields[1].fieldname == "import_type":
		return

	nts.db.sql("DROP TABLE IF EXISTS `tabData Import Legacy`")
	nts.rename_doc("DocType", "Data Import", "Data Import Legacy")
	nts.db.commit()
	nts.db.sql("DROP TABLE IF EXISTS `tabData Import`")
	nts.rename_doc("DocType", "Data Import Beta", "Data Import")
