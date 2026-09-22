import {
	CANVAS,
	DOCTYPE_PAGE,
	PAGE,
	ROUTE,
	SINGLE_PAGE_FIELDS,
	SPLITTABLE_FIELDS,
	WEB_FORM_PAGE,
	fill_new_web_form,
	open_builder,
	seed_web_form,
	web_form_fields,
} from "../support/web_form";

function page_labels_should_be(labels) {
	cy.get(`${CANVAS} .tab-header .tabs .tab`).should(($tabs) => {
		expect([...$tabs].map((tab) => tab.innerText.trim())).to.deep.eq(labels);
	});
}

function move_second_section_to_new_page() {
	const section = `${CANVAS} .tab-content.active .form-section-container:eq(1)`;
	cy.get(section).click(15, 10);
	cy.get(section).find(".dropdown-btn:first").click();
	cy.contains(".dropdown-options:visible .dropdown-item", "Move sections to new page").click();
}

function open_add_field_picker() {
	cy.get(`${CANVAS} .tab-content.active .section-columns-container:first .column:first`)
		.find(".add-new-field-btn button")
		.click();
}

context("Web Form Builder", () => {
	before(() => {
		cy.login();
		cy.visit("/desk");
	});

	it("Adds Copy embed code once on the first save", () => {
		fill_new_web_form("Embed Note New");

		// the first save renames the form, and that drives a second refresh
		cy.save();

		// the saved name routes to a second page, so scope to the Web Form one
		cy.get(`${WEB_FORM_PAGE} .user-action-link`)
			.filter(':contains("Copy embed code")')
			.should("have.length", 1);

		// removing the <a> alone leaves its row behind, and the list's gap still counts it
		cy.get(`${WEB_FORM_PAGE} .user-action-row:empty`).should("not.exist");
	});

	it("Adds page two to a form that has only page one", () => {
		seed_web_form(SINGLE_PAGE_FIELDS);
		open_builder();

		// like DocType, a single page has no header; page 2 is added from the sidebar
		cy.get(`${CANVAS} .tab-header`).should("not.exist");
		cy.get(`${CANVAS} .sidebar-container .new-tab-btn`).should("be.visible").click();

		cy.get(`${CANVAS} .tab-header .tabs .tab`).should("have.length", 2);
		cy.get(`${CANVAS} .tab-header .tabs .tab:last`).should("contain.text", "Page 2");

		// a page needs a field, or get_updated_fields() prunes its empty section away
		cy.get(`${CANVAS} .tab-content.active .section-columns-container:first .column:first`)
			.find(".empty-column .add-field-btn")
			.click();
		cy.get(".combo-box-options:visible .search-box > input").type("content{enter}");

		cy.click_doc_primary_button("Save");

		web_form_fields().then((fields) => {
			const page_breaks = fields.filter((f) => f.fieldtype === "Page Break");
			expect(page_breaks.length, "one break for two pages").to.eq(1);
			// the break opens page two, so a field added there follows it
			const break_idx = fields.findIndex((f) => f.fieldtype === "Page Break");
			const content_idx = fields.findIndex((f) => f.fieldname === "content");
			expect(content_idx, "content sits on page two").to.be.greaterThan(break_idx);
		});
	});

	it("Renumbers the pages after a page is inserted or deleted", () => {
		seed_web_form(SPLITTABLE_FIELDS);
		open_builder();

		// the new page goes in after page 1, so the old page 2 becomes page 3
		move_second_section_to_new_page();
		page_labels_should_be(["Page 1", "Page 2", "Page 3"]);
		cy.get(`${CANVAS} .tab-content.active [data-fieldname='public']`).should("exist");

		cy.get(`${CANVAS} .tab-header .tabs .tab:eq(1)`)
			.realHover()
			.find(".remove-tab-btn")
			.click();
		cy.click_modal_primary_button("Delete page");

		// the fields of the deleted page move back to page 1
		page_labels_should_be(["Page 1", "Page 2"]);
		cy.get(`${CANVAS} .tab-content.active [data-fieldname='public']`).should("exist");
	});

	it("Stops Move sections to new page at the page limit", () => {
		seed_web_form(SPLITTABLE_FIELDS);
		open_builder();

		for (let i = 0; i < 8; i++) {
			cy.get(`${CANVAS} .tab-header`).realHover().find(".tab-actions .new-tab-btn").click();
		}
		cy.get(`${CANVAS} .tab-header .tabs .tab`).should("have.length", 10);
		cy.get(`${CANVAS} .tab-header .tabs .tab:last`).should("contain.text", "Page 10");

		cy.get(`${CANVAS} .tab-header .tabs .tab:first`).click();
		move_second_section_to_new_page();

		// the limit names itself, so the dialog is not just an unexplained "Message"
		cy.get(".msgprint-dialog:visible .modal-title").should("contain.text", "Too Many Pages");
		cy.get(".msgprint").should("contain.text", "There can be only 9 Page Break fields");
		cy.get(`${CANVAS} .tab-header .tabs .tab`).should("have.length", 10);
	});

	it("Stops a tenth Page Break added from the fields grid", () => {
		// nine breaks already, so the row added below is the tenth
		const nine_breaks = Array.from({ length: 9 }, () => ({ fieldtype: "Page Break" }));
		seed_web_form([...SINGLE_PAGE_FIELDS, ...nine_breaks]);

		cy.visit(`/desk/web-form/${ROUTE}`);
		cy.findByRole("tab", { name: "Settings" }).click();
		cy.click_form_section("Fields");

		cy.get('[data-fieldname="web_form_fields"]').as("grid");
		cy.get("@grid").find("button.grid-add-row").click();
		cy.get("@grid").find(".grid-body .grid-row:last").as("new_row");
		cy.get("@new_row").find('[data-fieldname="fieldtype"]').click();
		cy.get("@new_row").find('[data-fieldname="fieldtype"] select').select("Page Break");

		// the same limit as the builder's, checked in the one place both call
		cy.get(".msgprint-dialog:visible .modal-title").should("contain.text", "Too Many Pages");
	});

	it("Lays the stored rows out as pages", () => {
		seed_web_form();
		open_builder();

		// one Page Break row, but two pages — page one is implicit
		cy.get(`${CANVAS} .tab-header .tabs .tab`).should("have.length", 2);
		cy.get(`${CANVAS} .tab-header .tabs .tab:first`).should("contain.text", "Page 1");
		cy.get(`${CANVAS} .tab-content.active [data-fieldname='title']`).should("exist");
		cy.get(`${CANVAS} .tab-content.active [data-fieldname='content']`).should("not.exist");
	});

	it("Does not dirty the form by rendering", () => {
		open_builder();

		// the rebuild on mount trips the change watcher, but must not mark the record edited
		cy.get('[data-testid="page-status"]').should("not.contain.text", "Not Saved");
	});

	it("Writes the pages back without inventing a Page Break for page one", () => {
		open_builder();

		cy.get(`${CANVAS} .tab-content.active .form-section-container:first`)
			.find("div[title='Double click to edit label']:first")
			.dblclick()
			.type("{selectall}Contact Details");

		cy.click_doc_primary_button("Save");

		web_form_fields().then((fields) => {
			const page_breaks = fields.filter((f) => f.fieldtype === "Page Break");
			expect(page_breaks.length, "page break rows for two pages").to.eq(1);
			expect(page_breaks[0].label, "page break label").to.be.oneOf([null, ""]);
		});
	});

	it("Keeps a section label through a save", () => {
		open_builder();

		web_form_fields().then((fields) => {
			const section = fields.find((f) => f.fieldtype === "Section Break" && f.label);
			expect(section, "labelled section break row").to.exist;
			expect(section.label).to.eq("Contact Details");
			// a structural row names no field of the source doctype
			expect(section.fieldname, "section break fieldname").to.be.oneOf([null, ""]);
		});
	});

	it("Offers the source doctype's own fields, not fieldtypes", () => {
		seed_web_form();
		open_builder();

		open_add_field_picker();

		// a field already on the canvas is not on offer, an unplaced one is
		cy.get(".combo-box-options:visible .combo-box-option").should("not.contain.text", "Title");
		cy.get(".combo-box-options:visible .search-box > input").type("public{enter}");

		cy.get(`${CANVAS} .tab-content.active [data-fieldname='public']`).should("exist");

		cy.click_doc_primary_button("Save");

		web_form_fields().then((fields) => {
			const placed = fields.filter((f) => f.fieldname === "public");
			expect(placed.length, "public appears once").to.eq(1);
			// the picker carries the source fieldtype over, not a chosen one
			expect(placed[0].fieldtype).to.eq("Check");
		});
	});

	it("Repoints the add-field picker when the DocType changes", () => {
		seed_web_form(SINGLE_PAGE_FIELDS);
		cy.visit(`/desk/web-form/${ROUTE}`);
		cy.get(CANVAS).should("exist");

		cy.fill_field("doc_type", "ToDo", "Link");

		cy.findByRole("tab", { name: "Form" }).click();
		open_add_field_picker();

		// the mounted builder is repointed in place, so it offers ToDo's fields now
		cy.get(".combo-box-options:visible").should("contain.text", "Priority");
		cy.get(".combo-box-options:visible").should("not.contain.text", "Content");
	});

	it("Picks up rows removed from the Settings tab", () => {
		seed_web_form();
		open_builder();

		cy.get(`${CANVAS} .tab-content.active [data-fieldname='title']`).should("exist");

		// the grid sits in the collapsed Fields section on Settings
		cy.findByRole("tab", { name: "Settings" }).click();
		cy.click_form_section("Fields");
		cy.get('[data-fieldname="web_form_fields"] .grid-row')
			.contains("Title")
			.parents(".grid-row")
			.find(".grid-row-check")
			.click();
		cy.get('[data-fieldname="web_form_fields"] .grid-footer button')
			.contains("Delete")
			.click();

		// a tab switch syncs neither editor, the canvas re-reads the rows on save
		cy.click_doc_primary_button("Save");

		cy.findByRole("tab", { name: "Form" }).click();
		cy.get(`${CANVAS} .tab-content [data-fieldname='title']`).should("not.exist");
	});

	// the popovers belong to the shared builder, but two builders can only be put on one
	// page from here, where a Web Form fixture is already seeded
	it("Shows the field picker in a builder opened without a page reload", () => {
		seed_web_form();

		// the DocType builder goes first, so its container comes first in the DOM
		cy.visit("/desk/doctype/ToDo");
		cy.get(DOCTYPE_PAGE).findByRole("tab", { name: "Form" }).click();
		cy.get(`${DOCTYPE_PAGE} ${CANVAS}`).should("be.visible");

		// set_route resolves before the form renders, so wait for the Web Form to be the
		// form on screen. Clicking a tab too early lands it on the DocType page, and the
		// builder tab of the Web Form stays closed.
		cy.window().then((win) => win.frappe.set_route("Form", "Web Form", ROUTE));
		cy.window().its("cur_frm.doc.name").should("eq", ROUTE);
		cy.get(WEB_FORM_PAGE).findByRole("tab", { name: "Form" }).click();
		cy.get(`${WEB_FORM_PAGE} ${CANVAS}`).should("be.visible");

		// the premise: both builders are on the page, and both own a teleport target
		cy.get(CANVAS).should("have.length", 2);
		cy.get(".autocomplete-area").should("have.length", 2);

		cy.get(
			`${WEB_FORM_PAGE} ${CANVAS} .tab-content.active .section-columns-container:first .column:first`
		)
			.find(".add-new-field-btn button")
			.click();

		// the picker used to teleport into the hidden DocType page and render off screen
		cy.get(".combo-box-options:visible").should("exist");
	});

	it("Steps the desk chrome aside on the builder tab", () => {
		seed_web_form();
		open_builder();

		// the canvas is full-bleed, so the timeline below it would only add dead scroll
		cy.get(`${PAGE} .form-footer`).should("not.be.visible");
		cy.window()
			.its("cur_frm")
			.should(
				(frm) =>
					expect(frm.form_wrapper.hasClass("mb-1"), "tight bottom margin").to.be.true
			);

		cy.get(PAGE).findByRole("tab", { name: "Settings" }).click();

		// `be.visible` reads the scroll position, it does not scroll, and the footer sits
		// below the Settings tab
		cy.get(`${PAGE} .form-footer`).scrollIntoView().should("be.visible");
		cy.window()
			.its("cur_frm")
			.should((frm) => expect(frm.form_wrapper.hasClass("mb-1")).to.be.false);
	});

	it("Keeps the sidebar hidden on the builder tab across a save", () => {
		seed_web_form();
		open_builder();

		cy.get(`${PAGE} .layout-side-section`).should("not.be.visible");

		// dirty the canvas, or the save is a no-op and never rebuilds the sidebar
		cy.get(`${PAGE} ${CANVAS} .tab-content.active .form-section-container:first`)
			.find("div[title='Double click to edit label']:first")
			.dblclick()
			.type("{selectall}Contact Details");
		cy.click_doc_primary_button("Save");

		// the save rebuilds the sidebar and clears `hide-sidebar`, the re-sync puts it back
		cy.get(`${PAGE} .layout-side-section`).should("not.be.visible");

		// and the rule is still a rule, not a permanent hide
		cy.get(PAGE).findByRole("tab", { name: "Settings" }).click();
		cy.get(`${PAGE} .layout-side-section`).should("be.visible");
	});

	it("Leaves the sidebar hidden on an unsaved form", () => {
		// Desk hides the sidebar of a new doc because it has nothing to show
		cy.visit("/desk/web-form/new");
		cy.get(`${PAGE} .layout-side-section`).should("not.be.visible");

		// move onto the builder tab and back off it, the path that asks for the sidebar.
		// Showing it here with an inline display would outrank Desk and leave an empty shell.
		cy.get(PAGE).findByRole("tab", { name: "Form" }).click();
		cy.get(PAGE).findByRole("tab", { name: "Settings" }).click();
		cy.get(`${PAGE} .layout-side-section`).should("not.be.visible");
	});
});
