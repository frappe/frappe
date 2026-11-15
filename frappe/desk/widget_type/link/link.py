import frappe
from frappe.desk.utils import is_item_allowed
from frappe.desk.widgets import WidgetType, desk_views

QUERY_REPORT_TYPES = ("Query Report", "Script Report", "Custom Report")


class Link(WidgetType):
	"""A link to a DocType, Report or Page, drawn as a row inside a card."""

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
		only_for = self.config.get("only_for")
		if only_for and only_for != frappe.db.get_default("country"):
			return None

		data = self.report_details() if self.link_type == "Report" else {}
		if missing := [d for d in split_list(self.config.get("dependencies")) if not has_records(d)]:
			data["incomplete_dependencies"] = missing
		if self.link_type == "DocType":
			data["description"] = frappe.get_meta(self.link_to).description
			if self.config.get("onboard"):
				data["count"] = has_records(self.link_to)
		return data

	def report_details(self) -> dict:
		report = desk_views().allowed_reports.get(self.link_to, {})
		if report.get("report_type") in QUERY_REPORT_TYPES:
			return {"is_query_report": 1}
		return {"ref_doctype": report.get("ref_doctype")}


def split_list(value: str | None) -> list[str]:
	return [part.strip() for part in (value or "").split(",") if part.strip()]


def has_records(doctype: str) -> bool:
	from frappe.desk.desktop import get_table_with_counts

	if get_table_with_counts().get(doctype):
		return True
	if not frappe.db.exists("DocType", doctype):
		return False
	return frappe.get_meta(doctype).issingle or bool(frappe.get_all(doctype, limit=1))
