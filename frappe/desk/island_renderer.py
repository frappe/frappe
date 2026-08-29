# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Lets an installed app draw a desk document with its own island.

An app declares a renderer against the document it draws:

    dashboard_renderer = "someapp.desk.dashboard.render"
    dashboard_chart_renderer = "someapp.desk.chart.render"

The method takes the document, and returns either `None` or the island that draws
it:

    def render(doc):
        if not doc.someapp_dashboard:
            return None
        return {"island": "someapp.dashboard", "props": {"dashboard": doc.someapp_dashboard}}

Framework forwards the document and takes the answer. It reads no field of the
app's own, so the app decides on a Custom Field, on a naming rule, or on anything
else it holds.

This seam is separate from the island registry in `frappe.utils.island`. The
registry is universal: it turns an island's name into a bundle, and it knows
nothing about documents. This module is desk's, and it knows only the documents
desk draws. A further document an app may draw adds a hook here, and the registry
stays as it is. The registry also stays the only place that knows whether an
island exists, so this module never checks a name.

The answer rides `__onload`, so the client reads it off the document it already
fetches.
"""

import frappe
from frappe import _

# The `__onload` key every renderable document answers on. The client reads this
# one name, whatever the doctype.
ONLOAD_KEY = "island_renderer"


def set_island_renderer(doc, hook: str) -> None:
	"""Put the island that draws `doc` on its `__onload`, if an app draws it.

	The key is absent when no app draws the document, so the client falls back to
	desk's own renderer on a missing key alone.
	"""
	renderer = resolve_island_renderer(doc, hook)
	if renderer:
		doc.set_onload(ONLOAD_KEY, renderer)


def resolve_island_renderer(doc, hook: str) -> dict | None:
	"""The island that draws `doc`, as `{"island": name, "props": {...}}`.

	Exactly one app may draw a document. Every declared renderer runs, so that a
	second app that claims the same document is named in the log rather than
	silently ignored. The first one still draws it, because a precedence rule
	would make the collision a feature.
	"""
	# `frappe.get_hooks` is cached, so a site where no app declares the hook pays
	# for this lookup and nothing else.
	methods = frappe.get_hooks(hook)
	if not methods:
		return None

	answers = {}
	for method in methods:
		answer = frappe.get_attr(method)(doc)
		if answer is not None:
			answers[method] = _validated(answer, method, hook)

	if not answers:
		return None

	drawn_by, renderer = next(iter(answers.items()))
	if len(answers) > 1:
		frappe.logger().warning(
			f"More than one app draws {doc.doctype} {doc.name}: {', '.join(answers)}. {drawn_by} draws it."
		)

	return renderer


def _validated(answer, method: str, hook: str) -> dict:
	"""The answer of `method`, reduced to the shape `__onload` carries."""
	if not isinstance(answer, dict):
		frappe.throw(
			_("{0} must return None or a dict, and returned {1}. It is declared as {2}.").format(
				method, type(answer).__name__, hook
			)
		)

	island = answer.get("island")
	if not island or not isinstance(island, str):
		frappe.throw(_("{0} returned a renderer that names no island: {1}").format(method, answer))

	props = answer.get("props") or {}
	if not isinstance(props, dict):
		frappe.throw(_("{0} returned props that are not a dict: {1}").format(method, props))

	return {"island": island, "props": props}
