// The `Sidebar` kind: the item that makes a rail item LINKED.
//
// #42227 decided that linked-versus-independent needs no field, because a `Sidebar` item
// IS the link. `link_to` carries the sidebar's scrubbed address, which is the key boot
// files it under (#42356), so opening one is a dictionary lookup on a value the item is
// already holding.
//
// What clicking it does is ORDINARY NAVIGATION, and that is charter point 7 rather than a
// convenience: the rail highlights whatever the current URL resolves to, so a rail item
// that only changed shell state would be a selection the address could not express and a
// paste could not reproduce. So this resolves to the first real destination inside the
// sidebar, and the sidebar key rides along as an annotation — which is what lets the panel
// (#42421) mount off it without this file learning what a panel is.
//
// A sidebar with no rows is absent from the payload rather than empty (#42356), and a
// linked item whose sidebar is absent renders as an independent one. Here that means: no
// destination, no annotation, skipped. It is not a state an authored rail should reach —
// `Sidebar` declares the `Derived From Children` permission rule, so the server's own
// cascade drops the item when its sidebar resolves to nothing — but the rail must not
// depend on a filter it does not run.

export default {
	render(item, { sidebars, renderingOf }) {
		const rows = sidebars[item.link_to];
		if (!rows?.length) return null;

		for (const row of rows) {
			const rendering = renderingOf(row);
			// A `group` has no destination and an `expand` is not one either — following an
			// item must not fire a request. Both are skipped, so a sidebar whose first row is
			// a section opens at the first thing under it, which is what a reader sees anyway.
			if (!rendering || !("to" in rendering || "href" in rendering)) continue;

			// The first row usually sits in several sidebars, so the address alone cannot say
			// which this item opens. In the href, not a handler: these are `RouterLink`s.
			if ("to" in rendering)
				return {
					...rendering,
					to: {
						...rendering.to,
						query: { ...rendering.to.query, sidebar: item.link_to },
					},
					sidebar: item.link_to,
				};

			// An `href` leaves the prefix, so there is no sidebar of ours to name.
			return { ...rendering, sidebar: item.link_to };
		}

		return null;
	},
};
