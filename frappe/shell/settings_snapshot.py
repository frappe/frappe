# SETTINGS SNAPSHOT — an app's resolved panes as JSON, so a test can pin them in a checked-in file.

import json
import os

import frappe

from .settings import resolve_panes

UPDATE_VARIABLE = "UPDATE_SETTINGS_SNAPSHOT"


def settings_snapshot(app: str) -> str:
	"""The unfiltered panes with `app`'s blocks, as they merge with frappe's panes and no other app's."""
	panes = []
	for pane in resolve_panes(list(dict.fromkeys(["frappe", app]))):
		blocks = [block for block in pane["blocks"] if block["app"] == app]
		if blocks:
			panes.append({**pane, "blocks": blocks})

	return json.dumps(panes, indent=1, sort_keys=True) + "\n"


def check_settings_snapshot(test, app: str, path: str):
	"""Fail `test` when the panes differ from the file at `path`; set `UPDATE_SETTINGS_SNAPSHOT=1` to rewrite it."""
	current = settings_snapshot(app)

	if os.environ.get(UPDATE_VARIABLE):
		frappe.create_folder(os.path.dirname(path))
		with open(path, "w") as handle:
			handle.write(current)

	with open(path) as handle:
		test.assertEqual(
			json.loads(current), json.load(handle), f"Run with {UPDATE_VARIABLE}=1 to update {path}"
		)
