// shared by the Web Form builder and Get Fields specs

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

export function web_form_fields() {
	return cy
		.window()
		.its("cur_frm")
		.then((frm) => frm.doc.web_form_fields || []);
}

// `remove_doc` and `insert_doc` need `frappe.csrf_token` from whatever page the previous
// test left behind, which may still be mid-navigation
export function wait_for_desk() {
	cy.window().should((win) =>
		expect(win.frappe?.csrf_token, "desk is loaded").to.be.a("string")
	);
}

export function seed_web_form(fields = SEEDED_FIELDS, overrides = {}) {
	const route = overrides.route || ROUTE;
	wait_for_desk();
	cy.remove_doc("Web Form", route, true);
	return cy.insert_doc(
		"Web Form",
		{
			title: "Builder Note",
			route: ROUTE,
			doc_type: "Note",
			module: "Website",
			web_form_fields: fields,
			...overrides,
		},
		true
	);
}

export function open_builder(route = ROUTE) {
	cy.visit(`/desk/web-form/${route}`);
	cy.findByRole("tab", { name: "Form" }).click();
	cy.get(CANVAS).should("exist");
}

// Get Fields flushes the builder before it reads the rows, so let the canvas mount first
export function open_get_fields(route = ROUTE) {
	cy.visit(`/desk/web-form/${route}`);
	cy.get(CANVAS).should("exist");
	cy.click_custom_action_button("Get Fields");
	return cy.get_open_dialog();
}

// an unsaved form, filled in through the UI and given fields by Get Fields. It saves under
// the route slugged from its title, so that is the name to clear first
export function fill_new_web_form(title) {
	wait_for_desk();
	cy.remove_doc("Web Form", title.toLowerCase().replace(/ /g, "-"), true);
	cy.visit("/desk/web-form/new");

	cy.fill_field("title", title);
	cy.fill_field("doc_type", "Note", "Link");
	cy.fill_field("module", "Website", "Link");

	cy.click_custom_action_button("Get Fields");
	cy.get_open_dialog().find('[data-action="select_all"]').click();
	cy.click_modal_primary_button("Update");
	cy.get('[data-fieldname="web_form_fields"] .grid-row').should("have.length.greaterThan", 0);
}
