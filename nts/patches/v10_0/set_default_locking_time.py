# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def execute():
	nts.reload_doc("core", "doctype", "system_settings")
	nts.db.set_single_value("System Settings", "allow_login_after_fail", 60)
