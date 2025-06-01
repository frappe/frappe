import nts
from nts.desk.doctype.notification_settings.notification_settings import (
	create_notification_settings,
)


def execute():
	nts.reload_doc("desk", "doctype", "notification_settings")
	nts.reload_doc("desk", "doctype", "notification_subscribed_document")

	users = nts.get_all("User", fields=["name"])
	for user in users:
		create_notification_settings(user.name)
