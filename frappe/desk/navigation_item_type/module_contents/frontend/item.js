// The `Module Contents` kind: whatever is left of a module.
//
// The only kind whose row count is not known when the payload is built, and the reason it
// exists at all. #42318 made it a kind rather than a filtered link, so that "an authored
// item never carries a query" holds with no exception: v1's "N more" overflow row is the
// one thing that ever AUTHORED a filter, and this is what replaced it.
//
// It is therefore also the one kind that costs a request, and the only one that may. The
// rule boot is built around is that a NAVIGATION click costs none (#42232); expanding a
// list is not navigating, and the alternative — every module's full contents in every
// boot — is exactly what put 41,701 bytes of workspace furniture into desk v1's.
//
// "What is left" is measured against the list on screen rather than against the module:
// a doctype an app put on its rail by hand must not appear twice, and only the list knows
// which those are.

export default {
	render(item, { addresses, items, contentsOf }) {
		const slug = addresses.slugOfModule(item.link_to);
		if (!slug) return null;

		return {
			expand: async () => {
				const shown = new Set(
					items
						.filter((entry) => entry.item_type === "DocType")
						.map((entry) => entry.link_to)
				);

				const entries = await contentsOf(slug);

				return entries
					.filter((entry) => !shown.has(entry.doctype))
					.map((entry) => ({
						// Namespaced under the row that produced it. These rows are not stored and
						// carry no arrangement, but they share a list with rows that do, and a
						// bare doctype name would collide with a derived item's key — which IS the
						// doctype name (`navigation.py`'s `_derive_rail`).
						key: `${item.key}:${entry.doctype}`,
						item_type: "DocType",
						link_doctype: "DocType",
						link_to: entry.doctype,
					}));
			},
		};
	},

	label(item) {
		return item.link_to;
	},
};
