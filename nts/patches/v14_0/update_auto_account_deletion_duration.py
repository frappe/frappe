import nts


def execute():
	days = nts.db.get_single_value("Website Settings", "auto_account_deletion")
	nts.db.set_single_value("Website Settings", "auto_account_deletion", days * 24)
