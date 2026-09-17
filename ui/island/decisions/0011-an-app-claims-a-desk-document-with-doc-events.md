# An app claims a desk document with `doc_events`

Desk draws `Dashboard` and `Dashboard Chart` itself. An app that keeps its own dashboards wants its island to draw them instead. Only the app knows which documents are its own.

## Decision

The island that draws a document is carried in `__onload.island`, as `{"name", "props"}`. `name` is a name the app declared in `ui_islands`. `props` is the island's props object. When the key is absent, desk draws the document.

The app sets the key from an `onload` handler it declares in `doc_events`:

```python
doc_events = {"Dashboard": {"onload": "someapp.desk.island.dashboard"}}

def dashboard(doc, method=None):
	if doc.someapp_dashboard:
		doc.set_onload("island", {"name": "someapp.dashboard", "props": {"dashboard": doc.someapp_dashboard}})
```

`Document.run_method("onload")` already composes every `doc_events` handler, and `frappe.desk.form.load` runs it for every document the client fetches. So framework adds nothing. The desk page and the chart widget read one `__onload` key. A further document an app may draw needs no framework change.

Framework reads no field of the app's own. The app decides on a Custom Field, on a naming rule, or on anything else it holds.

This seam is separate from the island registry in `frappe.utils.island`. The registry is universal. It turns a name into a bundle and knows nothing about documents. It stays the only place that knows whether an island exists.

## Rejected: a `dashboard_renderer` hook per document

A hook named for the document. Its method takes the document and returns the island or `None`. Framework ran every app's method, validated the answer, warned on a collision, and wrote the winner to `__onload`.

It re-implemented `doc_events` with a worse name. Every document desk draws needed a new hook, a new `onload` override, and a line in `hooks.py`. The validation and collision code guarded a shape only the app that returned it could get wrong. An app that gets it wrong sees the same result either way: its island does not draw. `doc_events` already orders the handlers of two apps. The second app overwrites the first, which is the same outcome the warning described.
