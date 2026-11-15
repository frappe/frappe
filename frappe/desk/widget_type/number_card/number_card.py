import frappe
from frappe.desk.doctype.number_card.number_card import get_result, percentage_difference
from frappe.desk.doctype.number_card.number_card import has_permission as can_read_card
from frappe.desk.widgets import WidgetType

# what each kind of card cannot be drawn without
NEEDS = {
	"Document Type": ["document_type", "function"],
	"Report": ["report_name", "report_field", "report_function"],
	"Custom": ["method"],
}


class NumberCard(WidgetType):
	"""A number with its change since the last period. The server works out a Document Type card;
	the renderer loads a Report or Custom card in the browser."""

	def has_permission(self, user=None) -> bool:
		return can_read_card(frappe._dict(self.config), "read", user)

	def validate(self):
		self.require(NEEDS.get(self.config.get("type"), []))

	def get_data(self, filters=None):
		if self.config.get("type") != "Document Type":
			return {}
		interval = (filters or {}).get("stats_time_interval") or self.config.get("stats_time_interval")
		card = frappe._dict(self.config, stats_time_interval=interval)
		rows = self.filters(filters)
		value = get_result(card, list(rows))
		data = {"value": value, "stats_time_interval": interval}
		if card.show_percentage_stats:
			data["delta"] = percentage_difference(card, list(rows), value)
		return data
