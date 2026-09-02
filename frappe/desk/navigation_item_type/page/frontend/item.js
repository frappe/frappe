// The `Page` kind: a page an app contributed.
//
// `link_to` is the page's SLUG, which is the page's whole identity in desk v2: a
// contributed page is a file at `<module>/frontend/pages/<slug>.js` and there is no
// record behind it. The type record's `target_doctype` still names v1's `Page` doctype,
// because that is what #42231's `Permitted Page` bucket reads on the server; the two are
// answering different questions and the disagreement is recorded on #42420 rather than
// resolved by guessing which one to break.
//
// A slug this prefix does not serve is skipped rather than linked. The route table holds
// only the DECLARING app's pages — a ten-app bench does not put ten apps' pages in one
// prefix (#42070) — so a link built for a page that is not in it resolves to the shell's
// not-found, one hop later and with the reason lost.

export default {
	render(item, { boot, pages }) {
		const page = pages.find((entry) => entry.slug === item.link_to);
		return page ? { to: { name: `page:${boot.app}:${page.slug}` } } : null;
	},

	label(item, { pages }) {
		return pages.find((entry) => entry.slug === item.link_to)?.title;
	},
};
