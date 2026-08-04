"""Marketplace: list the bench app catalog for this site and install, uninstall
or update apps through the bench pilot admin. All actions go over HTTP to the
site's bench; this module only shapes requests and merges the responses."""

from urllib.parse import quote

import frappe


def list_apps(client) -> dict:
	"""Merge the bench marketplace catalog with what is installed on this site.

	Catalog entries carry title/logo/category and an ``is_installable`` flag
	(whether a build compatible with the running Frappe version exists). We layer
	the site's installed versions on top to decide install / update / uninstall.

	Note: The endpoint from Pilot provides entire list of apps, it would be ideal if we eventually add pagination to API and also add infinite scroll to the frontend.
	"""
	# Site-scoped catalog route: the bench-wide /marketplace/apps needs a bench
	# token, which the site doesn't hold, so pilot exposes the same catalog under
	# the site.
	catalog = client.get(client.site_path("marketplace"))
	if not isinstance(catalog, list):
		catalog = []
	installed = _installed_versions(client)

	apps = [_app_row(entry, installed) for entry in catalog if entry.get("name")]
	# the apps also includes Framework. We should not show framework in the catalog.
	apps = [app for app in apps if app["name"] != "frappe"]
	apps.sort(key=_sort_key)

	categories = sorted({app["category"] for app in apps if app["category"]})
	update_count = sum(1 for app in apps if app["has_update"])
	return {"apps": apps, "categories": categories, "update_count": update_count}


def install(client, app: str) -> dict:
	"""Clone (if needed) and install a catalog app on the site. The bench resolves
	the repo and compatible target from the marketplace app name. Returns the
	bench task (task_id) the UI polls to completion."""
	return client.post(client.site_path("apps"), {"app": _clean(app)})


def uninstall(client, app: str) -> dict:
	return client.delete(client.site_path(f"apps/{quote(_clean(app), safe='')}"))


def update(client, apps: str | None) -> dict:
	"""Pull and migrate apps in the background. ``apps`` is an optional JSON list
	of names; omit it to update everything."""
	names = frappe.parse_json(apps) if apps else None
	args = {}
	if names:
		args["apps"] = [_clean(name) for name in names]
	return client.post(client.site_path("actions/update-apps"), args)


def _installed_versions(client) -> dict:
	apps = client.get(client.site_path("apps")).get("apps", [])
	return {app["name"]: app.get("version") or "" for app in apps if app.get("name")}


def _app_row(entry: dict, installed: dict) -> dict:
	name = entry["name"]
	installed_version = installed.get(name, "")
	latest_version = entry.get("version") or ""
	return {
		"name": name,
		"title": entry.get("title") or name,
		"description": entry.get("description") or "",
		"logo_url": entry.get("logo_url") or "",
		"category": entry.get("category") or "",
		"stars": entry.get("stars") or 0,
		"installable": bool(entry.get("is_installable")),
		"required_version": entry.get("required_version") or "",
		"installed": name in installed,
		"installed_version": installed_version,
		"latest_version": latest_version,
		"has_update": bool(installed_version) and _is_newer(latest_version, installed_version),
	}


def _sort_key(app: dict) -> tuple:
	"""Installed apps first, then most-starred, then alphabetical."""
	return (not app["installed"], -app["stars"], app["title"].lower())


def _is_newer(latest: str, current: str) -> bool:
	latest_parts, current_parts = _version_tuple(latest), _version_tuple(current)
	if not latest_parts or not current_parts:
		return False
	return latest_parts > current_parts


def _version_tuple(version: str) -> tuple:
	parts = []
	for chunk in version.split("."):
		number = "".join(char for char in chunk if char.isdigit())
		if not number:
			break
		parts.append(int(number))
	return tuple(parts)


def _clean(name: str) -> str:
	name = (name or "").strip()
	if not name:
		frappe.throw(frappe._("App name is required."), frappe.ValidationError)
	return name
