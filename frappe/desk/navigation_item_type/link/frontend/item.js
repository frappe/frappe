// The `Link` kind: a URL its author chose, pointing wherever they pointed it.
//
// The only kind that is `Always Visible`, and the only one that is never a `RouterLink`:
// its destination is outside this document's router by definition, so following it is a
// full page load. The server leaves it alone for the same reason — a `Link` row is the one
// contributed item `switches_app` says nothing about, because it already goes wherever it
// goes (`navigation.py`'s `_switching_url`).

export default {
	render(item) {
		return item.url ? { href: item.url } : null;
	},

	label(item) {
		return item.url;
	},
};
