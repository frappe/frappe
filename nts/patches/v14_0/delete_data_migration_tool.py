# Copyright (c) 2022, nts Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import nts


def execute():
	doctypes = nts.get_all("DocType", {"module": "Data Migration", "custom": 0}, pluck="name")
	for doctype in doctypes:
		nts.delete_doc("DocType", doctype, ignore_missing=True)

	nts.delete_doc("Module Def", "Data Migration", ignore_missing=True, force=True)
