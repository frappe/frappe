import nts
from nts.model.rename_doc import rename_doc


def execute():
	if nts.db.table_exists("Standard Reply") and not nts.db.table_exists("Email Template"):
		rename_doc("DocType", "Standard Reply", "Email Template")
		nts.reload_doc("email", "doctype", "email_template")
