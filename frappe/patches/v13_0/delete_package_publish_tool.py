# Copyright (c) 2020, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def execute():
	nts.delete_doc("DocType", "Package Publish Tool", ignore_missing=True)
	nts.delete_doc("DocType", "Package Document Type", ignore_missing=True)
	nts.delete_doc("DocType", "Package Publish Target", ignore_missing=True)
