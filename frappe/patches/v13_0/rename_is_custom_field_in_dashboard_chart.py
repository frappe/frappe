import nts
from nts.model.utils.rename_field import rename_field


def execute():
	if not nts.db.table_exists("Dashboard Chart"):
		return

	nts.reload_doc("desk", "doctype", "dashboard_chart")

	if nts.db.has_column("Dashboard Chart", "is_custom"):
		rename_field("Dashboard Chart", "is_custom", "use_report_chart")
