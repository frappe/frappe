// The `Module` kind: a module's landing page.
//
// `link_to` is the module's NAME; the address is its slug, and the slug comes off the
// address table rather than from a re-implementation of `frappe.scrub` here — the same
// rule `addresses.ts` states for itself. The server sends both halves so neither side has
// to guess the other.
//
// Modular prefixes only, and that is a property of the APP rather than of the module
// (#42211 §2). Under a non-modular prefix there is no module route to land on, so the
// item has no destination here and is skipped — which is what the server already decided
// for the same case when a contributed module item tries to switch apps
// (`navigation.py`'s `_no_address`).

import { isModular, routeForModule } from "@shell";

export default {
	render(item, { addresses, boot }) {
		if (!isModular(boot)) return null;

		const slug = addresses.slugOfModule(item.link_to);
		return slug ? { to: routeForModule(slug) } : null;
	},

	label(item) {
		return item.link_to;
	},
};
