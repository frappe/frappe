// The `DocType` kind: a doctype's list.
//
// `link_to` IS the doctype — this is the one kind whose destination needs no second
// column, which is why `link_doctype` is filled by the schema rather than by a controller
// (#42340). It is also the only kind a derived rail produces, so this file draws every
// rail on the bench until an app ships rows.

import { routeFor } from "@shell";

export default {
	// `routeFor` and never a hand-built path. The address gained a module segment when an
	// app could declare `app_modular` (#42211), so `/${slug}` resolves under a modular
	// prefix — to the MODULE route, showing a page that is not the list. A 404 would be
	// kinder. `frappe/tests/test_shell.py` fails the build over it.
	render(item) {
		return { to: routeFor(item.link_to) };
	},

	label(item) {
		return item.link_to;
	},
};
