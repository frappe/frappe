from frappe.desk.widgets import WidgetType, build_widgets


class Card(WidgetType):
	"""A card of Link widgets. Each link is checked and cached on its own."""

	cache_ttl = 0

	def get_data(self, filters=None):
		names = [row["widget"] for row in self.config.get("widgets") or []]
		items = [card_item(link) for link in build_widgets(names).values()]
		return {"items": items} if items else None


def card_item(link: dict) -> dict:
	"""A link widget's payload as one row the card renderer draws."""
	return {"name": link["name"], "label": link["label"], **link["config"], **link["data"]}
