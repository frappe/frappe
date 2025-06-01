# Copyright (c) 2020, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def execute():
	if nts.db.exists("DocType", "Onboarding"):
		nts.rename_doc("DocType", "Onboarding", "Module Onboarding", ignore_if_exists=True)
