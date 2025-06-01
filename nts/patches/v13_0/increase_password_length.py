import nts


def execute():
	nts.db.change_column_type("__Auth", column="password", type="TEXT")
