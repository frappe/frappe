import nts


def execute():
	if nts.db.table_exists("Prepared Report"):
		nts.reload_doc("core", "doctype", "prepared_report")
		prepared_reports = nts.get_all("Prepared Report")
		for report in prepared_reports:
			nts.delete_doc("Prepared Report", report.name)
