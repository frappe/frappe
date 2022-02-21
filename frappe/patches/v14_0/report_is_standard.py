from frappe import qb


def execute():
	report = qb.DocType("Report")
	qb.update(report).set(report.is_standard, 1).where(report.is_standard == "Yes")
	qb.update(report).set(report.is_standard, 0).where(report.is_standard == "No")
