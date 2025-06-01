# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def execute():
	nts.delete_doc_if_exists("DocType", "User Permission for Page and Report")
