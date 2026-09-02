// The `Record` kind: one document.
//
// The one kind that carries its own `link_doctype` rather than having it fetched from the
// type (#42340), because the doctype and the record are two different answers and the
// pair is the address.

import { routeFor } from "@shell";

export default {
	render(item) {
		return { to: routeFor(item.link_doctype, item.link_to) };
	},

	// The record's NAME, not its title. The rail has no document to read a title from and
	// fetching one per row would be the per-request cost boot exists to avoid; an item
	// worth a title on the rail is an item worth an authored label.
	label(item) {
		return item.link_to;
	},
};
