// A rail the shipped one cannot change: every shipped row hidden at site level, then plain Link rows.
// It hides whatever the site layer lists for the app, so a spec names none of the shipped rows.
const APP = "frappe";
const GET = "frappe.shell.arrangement.get_arrangement";
const SAVE = "frappe.shell.arrangement.save_arrangement";
const RESET = "frappe.shell.arrangement.reset_arrangement";

/** `links` are `[key, label, url]`; a key is six lowercase letters or digits. */
export async function use_plain_rail(api, links) {
	const shipped = (await api.call(GET, { container: "Rail", address: APP, scope: "site" }))
		.message;
	const own = links.map(([key, label, url]) => ({
		key: `site:${key}`,
		item_type: "Link",
		label,
		url,
		added: 1,
	}));
	const items = [...shipped.map((row) => ({ ...row, hidden: 1 })), ...own];
	await api.call(SAVE, { container: "Rail", address: APP, items, scope: "site" });
}

export async function reset_plain_rail(api) {
	await api.call(RESET, { container: "Rail", address: APP, scope: "site" });
}
