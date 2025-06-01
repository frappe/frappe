import nts


def execute():
	singles = nts.qb.Table("tabSingles")
	nts.qb.from_(singles).delete().where(
		(singles.doctype == "System Settings") & (singles.field == "is_first_startup")
	).run()
