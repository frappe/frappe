import frappe
from frappe.desk.widget_type.link.link import Link


class Shortcut(Link):
	"""A tile that opens a DocType, Report, Page, Dashboard or URL, with a count of its records."""

	link_type_field = "type"

	def has_permission(self, user=None) -> bool:
		return self.link_type == "URL" or super().has_permission(user)

	def get_data(self, filters=None):
		domain = self.config.get("restrict_to_domain")
		if domain and domain not in frappe.get_active_domains():
			return None
		data = super().get_data(filters)
		if self.counts():
			data["count"] = self.count(self.link_to, self.filters(key="stats_filter"))
		return data

	def counts(self) -> bool:
		return (
			self.link_type == "DocType"
			and self.config.get("doc_view") != "New"
			and not frappe.get_meta(self.link_to).issingle
		)
