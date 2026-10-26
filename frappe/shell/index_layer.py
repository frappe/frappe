# INDEX LAYER — a person's own order and hidden apps on the index, over the app layer's tiles.
# A site layer, when built, sits between `index_tiles` (the app layer) and this one, in `arrange`.

import json

from frappe.model.utils.user_settings import get_user_settings, update_user_settings

from . import SHELL_ROOT

# The `__UserSettings` row the layer is kept under: the index's address, which no DocType can be named.
SETTINGS_KEY = f"/{SHELL_ROOT}"


def arrange(tiles: list[dict]) -> list[dict]:
	"""The app layer's tiles in the person's order, an app it does not name last, each marked `hidden`."""
	layer = read_layer()
	rank = {app: position for position, app in enumerate(layer["order"])}
	hidden = set(layer["hidden"])
	ordered = sorted(tiles, key=lambda tile: rank.get(tile["app"], len(rank)))

	return [{**tile, "hidden": tile["app"] in hidden} for tile in ordered]


def write_layer(order: list[str], hidden: list[str], tiles: list[dict]) -> None:
	"""Store the session user's layer over these app layer tiles, keeping only names they hold."""
	known = [tile["app"] for tile in tiles]
	order = _names(order, known)
	# An order that matches the app layer stores nothing, so a later `sequence_id` still places the app.
	if order == known:
		order = []

	hidden = _names(hidden, known)
	stored = {"order": order, "hidden": hidden} if order or hidden else {}
	# `for_update` replaces the row; without it user settings merge into what is there.
	update_user_settings(SETTINGS_KEY, json.dumps(stored), for_update=True)


def read_layer() -> dict:
	"""The session user's layer; a row that is not one reads as empty."""
	try:
		stored = json.loads(get_user_settings(SETTINGS_KEY))
	except ValueError:
		stored = None

	if not isinstance(stored, dict):
		stored = {}

	return {"order": _strings(stored.get("order")), "hidden": _strings(stored.get("hidden"))}


def _names(names: list[str], known: list[str]) -> list[str]:
	"""The names that have a tile, each once, in the order sent."""
	return list(dict.fromkeys(name for name in names if name in known))


def _strings(value) -> list[str]:
	return [name for name in value if isinstance(name, str)] if isinstance(value, list) else []
