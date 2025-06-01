import nts


def execute():
	table = nts.qb.DocType("Report")
	nts.qb.update(table).set(table.prepared_report, 0).where(table.disable_prepared_report == 1)
