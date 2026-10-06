import { expect } from "@playwright/test";

// a Desk tab panel is also a .tab-content, and Web Form has a "title" field of its
// own, so an unscoped [data-fieldname] query reaches the Desk control
export const CANVAS = ".form-builder-container";

// Desk hides the page it leaves instead of removing it, so a route change leaves two
// form pages in the DOM. Scope to the one on screen
export const PAGE = ".page-container:visible";

// a form page is named after its doctype. While a route change is still in flight the
// page on screen is still the old one, so `:visible` cannot tell the two apart
export const WEB_FORM_PAGE = ".page-container[data-page-route='Web Form']";
export const DOCTYPE_PAGE = ".page-container[data-page-route='DocType']";

export const ROUTE = "builder-note";

// two pages: the Page Break is the boundary, page one is implicit and has no row.
// "public" is left out so the add-field picker has something unplaced to offer
export const SEEDED_FIELDS = [
	{ fieldname: "title", label: "Title", fieldtype: "Data", reqd: 1 },
	{ fieldtype: "Page Break" },
	{ fieldname: "content", label: "Content", fieldtype: "Text Editor" },
];

// never split: no Page Break row, so the builder shows one page
export const SINGLE_PAGE_FIELDS = [
	{ fieldname: "title", label: "Title", fieldtype: "Data", reqd: 1 },
];

// page one has a second section, so "Move sections to new page" is on offer
export const SPLITTABLE_FIELDS = [
	{ fieldname: "title", label: "Title", fieldtype: "Data", reqd: 1 },
	{ fieldtype: "Section Break" },
	{ fieldname: "public", label: "Public", fieldtype: "Check" },
	{ fieldtype: "Page Break" },
	{ fieldname: "content", label: "Content", fieldtype: "Text Editor" },
];

export function web_form_fields(page) {
	return page.evaluate(() => cur_frm.doc.web_form_fields || []);
}

export async function expect_web_form_fields(page, assert) {
	await expect(async () => assert(await web_form_fields(page))).toPass({ timeout: 20000 });
}

// a delete that fails for any reason other than "not there" would leave the old rows in
// place, and the insert after it would then pass as a duplicate
async function delete_web_form(api, name) {
	const res = await api.request.delete(`/api/resource/Web Form/${name}`, {
		headers: await api.headers(),
	});
	expect([202, 404], `delete Web Form ${name}: ${await res.text()}`).toContain(res.status());
}

// every delete queues a background job, and SQLite refuses a write that overlaps one as
// "database is locked", so the writes here are retried
export async function remove_web_form(api, name) {
	await expect(() => delete_web_form(api, name)).toPass({ timeout: 20000 });
}

// a Web Form is named after its scrubbed title, so `doc.route` has to match it
export async function replace_web_form(api, doc) {
	let inserted;
	await expect(async () => {
		await delete_web_form(api, doc.route);
		inserted = await api.insert_doc("Web Form", doc);
	}).toPass({ timeout: 20000 });
	return inserted;
}

export function seed_web_form(api, fields = SEEDED_FIELDS, overrides = {}) {
	return replace_web_form(api, {
		title: "Builder Note",
		route: ROUTE,
		doc_type: "Note",
		module: "Website",
		web_form_fields: fields,
		...overrides,
	});
}

export async function open_builder(page, route = ROUTE) {
	await page.goto(`/desk/web-form/${route}`);
	await page.getByRole("tab", { name: "Form", exact: true }).click();
	await expect(page.locator(CANVAS)).toBeAttached();
}

// Get Fields flushes the builder before it reads the rows, so let the canvas mount first
export async function open_get_fields(desk, route = ROUTE) {
	await desk.page.goto(`/desk/web-form/${route}`);
	await expect(desk.page.locator(CANVAS)).toBeAttached();
	await desk.click_custom_action_button("Get Fields");
	return desk.get_open_dialog();
}

// an unsaved form, filled in through the UI and given fields by Get Fields. It saves under
// the route slugged from its title, so that is the name to clear first
export async function fill_new_web_form(desk, title) {
	const { page } = desk;
	await remove_web_form(desk.api, title.toLowerCase().replace(/ /g, "-"));
	await page.goto("/desk/web-form/new");

	await desk.fill_field("title", title);
	await desk.fill_field("doc_type", "Note", "Link");
	await desk.fill_field("module", "Website", "Link");

	await desk.click_custom_action_button("Get Fields");
	await desk.get_open_dialog().locator('[data-action="select_all"]').click();
	await desk.click_modal_primary_button("Update");
	await expect(page.locator('[data-fieldname="web_form_fields"] .grid-row')).not.toHaveCount(0);
}
