# SETTINGS SIDEBAR TEXT — the sidebar as the text the command prints and an app's `sidebar.txt` holds.

# One format for both, so a change reads as a short diff. An app's test calls `assert_settings_sidebar`.

import difflib
import json
from pathlib import Path

import frappe
from frappe.desk.settings_rules import report

from .registry import resolve_prefix
from .settings import merge_settings
from .settings_filter import SettingsFilter
from .settings_sidebar import Resolved, filter_sidebar

SIDEBAR_FILE = ("settings_dialog", "sidebar.txt")


def assert_settings_sidebar(prefix: str):
	"""Fail with a diff when the sidebar of `prefix` differs from its app's `settings_dialog/sidebar.txt`."""
	app, current = _snapshot(prefix)
	path = Path(frappe.get_app_path(app, *SIDEBAR_FILE))
	expected = path.read_text() if path.exists() else ""

	if current != expected:
		diff = "".join(
			difflib.unified_diff(
				expected.splitlines(keepends=True),
				current.splitlines(keepends=True),
				"sidebar.txt",
				"resolved",
			)
		)
		raise AssertionError(
			f"The sidebar of {prefix} differs from {path}. "
			f"Review it, then run: bench --site <site> settings-sidebar {prefix} --write\n{diff}"
		)


def write_settings_sidebar(prefix: str) -> Path:
	app, current = _snapshot(prefix)
	path = Path(frappe.get_app_path(app, *SIDEBAR_FILE))
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(current)
	return path


def describe_sidebars(prefix: str | None = None, *, as_json: bool = False, user: str | None = None) -> str:
	"""What the command prints: the sidebar of `prefix` (every prefix when blank), unfiltered or as `user` sees it."""
	resolved = merge_settings()
	if prefix and prefix not in resolved.sidebars:
		raise ValueError(
			f"No desk has the prefix {prefix}. Desks with a sidebar: {', '.join(resolved.sidebars)}."
		)

	sidebars = resolved.sidebars
	if user:
		frappe.set_user(user)  # nosemgrep
		panes = SettingsFilter().filter(resolved.panes)["panes"]
		sidebars = {key: filter_sidebar(sidebar, panes) for key, sidebar in sidebars.items()}

	wanted = [prefix] if prefix else list(sidebars)
	if as_json:
		return json.dumps({key: sidebars[key] for key in wanted}, indent=1)

	return "\n".join(sidebar_text(key, resolved, sidebars[key]) for key in wanted)


def sidebar_text(prefix: str, resolved: Resolved, sidebar: dict | None = None) -> str:
	"""The sidebar of `prefix` (or the given, filtered one) as text, with its notices."""
	sidebar = sidebar or resolved.sidebars[prefix]
	lines = [f"Sidebar {prefix}"]

	for group in sidebar["groups"]:
		lines += ["", _group_line(group)]
		for entry in group["panes"]:
			lines.append(f"  {entry['pane']}")
			lines += [f"    {block}{_note(block, entry['pane'], resolved)}" for block in entry["blocks"]]

	lines += ["", *[f"Hidden: {address}" for address in [*sidebar["hidden"], *sidebar["hidden_blocks"]]]]
	lines += [f"Notice: {notice}" for notice in resolved.notices.get(prefix, [])]
	return "\n".join(lines).rstrip() + "\n"


def required_scope(app: str) -> list[str]:
	"""Frappe, the apps `app` requires (and theirs), then `app`: the apps its snapshot resolves over."""
	from frappe.installer import parse_required_app_name

	scope: list[str] = []

	def add(name: str):
		for requirement in frappe.get_hooks("required_apps", app_name=name):
			add(parse_required_app_name(requirement))
		if name not in scope:
			scope.append(name)

	add(app)
	return ["frappe", *[name for name in scope if name != "frappe"]]


def _snapshot(prefix: str) -> tuple[str, str]:
	"""`(app, text)` of the sidebar of `prefix` over the app's required apps, raising on a bad arrangement."""
	app = resolve_prefix(prefix)
	if not app:
		raise ValueError(f"No active app has the prefix {prefix}.")

	resolved = merge_settings(required_scope(app))
	report(resolved.problems)
	return app, sidebar_text(prefix, resolved)


def _group_line(group: dict) -> str:
	if "label" in group:
		return f'Group "{group["label"]}"'
	if "app" in group:
		return f"Group of app {group['app']}"
	return "Group"


def _note(block: str, pane: str, resolved: Resolved) -> str:
	"""`added by <record>` for a block an extending app put in its host's pane; `placed` for one homed elsewhere."""
	home = block.rsplit("/", 1)[0]
	notes = []
	wire = resolved.directory.blocks.get(block)

	if wire and wire["app"] != resolved.directory.panes[home]["app"]:
		notes.append(f"added by {wire['app']}-{resolved.directory.panes[home]['app']}")
	if home != pane:
		notes.append(f"placed, home {home}")

	return f"  [{'; '.join(notes)}]" if notes else ""
