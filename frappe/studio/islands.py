import frappe

ISLAND_PREFIX = "frappe.studio."


def get_island_assets() -> dict:
	"""An island for each built Studio app with published pages, named `frappe.studio.<app>`."""
	assets = {}
	for app_name in frappe.get_all("Studio Page", {"published": 1}, pluck="studio_app", distinct=True):
		island = frappe.get_cached_doc("Studio App", app_name).get_assets_from_manifest("island")
		if not island:
			continue
		name = ISLAND_PREFIX + app_name
		assets[f"{name}.island.js"] = island["script"]
		if island["stylesheets"]:
			assets[f"{name}.island.css"] = island["stylesheets"][0].removesuffix(".css") + ".host.css"
	return assets
