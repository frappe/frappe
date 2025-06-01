import nts


def execute():
	nts.reload_doctype("Letter Head")

	# source of all existing letter heads must be HTML
	nts.db.sql("update `tabLetter Head` set source = 'HTML'")
