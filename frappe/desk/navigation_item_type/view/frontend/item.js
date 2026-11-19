// The `View` kind: one view of one doctype, a saved view or a plain view type.
//
// `link_to` is the doctype and `payload.view` the view's key, the same address Recent visits use.

import { routeFor } from "@shell";

export default {
	icon: "list",

	// A single has no list, so it has no view to open.
	render(item, { addresses }) {
		const key = item.payload?.view;
		if (!item.link_to || !key || addresses.isSingle(item.link_to)) return null;

		return { to: routeFor(item.link_to, null, { view: key }) };
	},

	// The editor writes a label when it adds the row; this is the last fallback.
	label(item, { boot }) {
		const key = item.payload?.view;
		const type = boot.view_types?.find((type) => type.name.toLowerCase() === key);

		return type?.label ?? key;
	},
};
