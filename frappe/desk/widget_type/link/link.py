import frappe
from frappe.desk.utils import is_item_allowed
from frappe.desk.widgets import WidgetType, desk_views

QUERY_REPORT_TYPES = ("Query Report", "Script Report", "Custom Report")


class Link(WidgetType):
	"""A link to a DocType, Report or Page."""

	link_type_field = "link_type"

	@property
	def link_type(self) -> str | None:
		return self.config.get(self.link_type_field)

	@property
	def link_to(self) -> str | None:
		return self.config.get("link_to")

	def has_permission(self, user=None) -> bool:
		return bool(self.link_to) and is_item_allowed(self.link_to, self.link_type, desk_views())

	def get_data(self, filters=None):
		return self.report_details() if self.link_type == "Report" else {}

	def report_details(self) -> dict:
		report = desk_views().allowed_reports.get(self.link_to, {})
		if report.get("report_type") in QUERY_REPORT_TYPES:
			return {"is_query_report": 1}
		return {"ref_doctype": report.get("ref_doctype")}
