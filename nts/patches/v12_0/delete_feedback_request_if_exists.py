import nts


def execute():
	nts.db.delete("DocType", {"name": "Feedback Request"})
