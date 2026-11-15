from frappe.desk.widgets import WidgetType, build_widget


class Card(WidgetType):
	"""A card of Link widgets. Each link is checked and cached on its own."""

	cache_ttl = 0

	def get_data(self, filters=None):
		names = [row["widget"] for row in self.config.get("widgets") or []]
		items = [card_item(link) for name in names if (link := build_widget(name))]
		return {"items": items} if items else None


def card_item(link: dict) -> dict:
	"""A link widget's payload as one row the card renderer draws."""
	return {"name": link["name"], "label": link["label"], **link["config"], **link["data"]}
