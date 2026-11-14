// The `Link` kind: a URL its author chose, pointing wherever they pointed it.
//
// The only kind that is `Always Visible`. A path inside this prefix is a route; any other path on
// this site is a full page load in place; another origin opens in a new tab, marked `external`.
// The server leaves it alone for the same reason — a `Link` row is the one contributed item
// `switches_app` says nothing about, because it already goes wherever it goes (`navigation.py`'s
// `_switching_url`).

export default {
	icon: "link",

	render(item, { boot, router }) {
		if (!item.url) return null;

		const path = sitePath(item.url);
		if (path === null) return { href: item.url, external: true };

		const inside = insidePrefix(path, boot.shell_base, router);
		return inside ? { to: inside } : { href: path };
	},

	label(item) {
		return item.url;
	},
};

// The path, query and hash of a URL on this site, or null for another origin.
function sitePath(url) {
	if (url.startsWith("/")) return url;

	try {
		const { origin, pathname, search, hash } = new URL(url, window.location.origin);
		return origin === window.location.origin ? pathname + search + hash : null;
	} catch {
		return null;
	}
}

// The prefix-relative path when the router serves it: a route that is not the not-found catch-all.
function insidePrefix(path, base, router) {
	const rest = base && path.startsWith(base) ? path.slice(base.length) : null;
	if (rest === null || !/^([/?#]|$)/.test(rest)) return null;

	const relative = rest.startsWith("/") ? rest : `/${rest}`;
	const resolved = router.resolve(relative);
	return resolved.matched.length && resolved.name !== "not-found" ? relative : null;
}
