# Copyright (c) 2020, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def execute():
	nts.reload_doc("Email", "doctype", "Notification")

	notifications = nts.get_all("Notification", {"is_standard": 1}, {"name", "channel"})
	for notification in notifications:
		if not notification.channel:
			nts.db.set_value("Notification", notification.name, "channel", "Email", update_modified=False)
			nts.db.commit()
