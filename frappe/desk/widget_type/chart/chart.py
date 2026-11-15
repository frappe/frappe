import frappe
from frappe.desk.widgets import WidgetType


class Chart(WidgetType):
	"""A Dashboard Chart. The base class checks the reader may read it."""

	# the reader's own chart settings change it, and reading them is one query
	cache_ttl = 0

	def get_data(self, filters=None):
		return {"chart_settings": user_chart_settings().get(self.config.get("chart")) or {}}


def user_chart_settings() -> dict:
	config = frappe.db.get_value("Dashboard Settings", frappe.session.user, "chart_config")
	return frappe.parse_json(config) or {}
