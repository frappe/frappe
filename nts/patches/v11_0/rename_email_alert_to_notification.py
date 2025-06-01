import nts
from nts.model.rename_doc import rename_doc


def execute():
	if nts.db.table_exists("Email Alert Recipient") and not nts.db.table_exists(
		"Notification Recipient"
	):
		rename_doc("DocType", "Email Alert Recipient", "Notification Recipient")
		nts.reload_doc("email", "doctype", "notification_recipient")

	if nts.db.table_exists("Email Alert") and not nts.db.table_exists("Notification"):
		rename_doc("DocType", "Email Alert", "Notification")
		nts.reload_doc("email", "doctype", "notification")
