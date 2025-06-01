# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def execute():
	nts.reload_doc("core", "doctype", "system_settings", force=1)
	nts.db.set_single_value("System Settings", "password_reset_limit", 3)
