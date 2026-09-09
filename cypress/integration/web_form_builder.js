const ROUTE = "builder-note";

// two pages: the Page Break is the boundary, page one is implicit and has no row.
// "public" is left out so the add-field picker has something unplaced to offer.
const SEEDED_FIELDS = [
	{ fieldname: "title", label: "Title", fieldtype: "Data", reqd: 1 },
	{ fieldtype: "Page Break" },
	{ fieldname: "content", label: "Content", fieldtype: "Text Editor" },
];

function web_form_fields() {
	return cy
		.window()
		.its("cur_frm")
		.then((frm) => frm.doc.web_form_fields || []);
}

function open_builder() {
	cy.visit(`/desk/web-form/${ROUTE}`);
	cy.findByRole("tab", { name: "Form" }).click();
	cy.get(".form-builder-container").should("exist");
}

// never split: no Page Break row, so the builder shows one page
const SINGLE_PAGE_FIELDS = [{ fieldname: "title", label: "Title", fieldtype: "Data", reqd: 1 }];

function seed_web_form(fields = SEEDED_FIELDS) {
	cy.remove_doc("Web Form", ROUTE, true);
	return cy.insert_doc(
		"Web Form",
		{
			title: "Builder Note",
			route: ROUTE,
			doc_type: "Note",
			module: "Website",
			web_form_fields: fields,
		},
		true
	);
}

context("Web Form Builder", () => {
	before(() => {
		cy.login();
		cy.visit("/desk");
	});

	it("Get Fields survives the first save", () => {
		// the builder mounts with an empty grid, and must not write that back over Get Fields
		cy.remove_doc("Web Form", "builder-note-new", true);
		cy.visit("/desk/web-form/new");

		cy.fill_field("title", "Builder Note New");
		cy.fill_field("doc_type", "Note", "Link");
		cy.fill_field("module", "Website", "Link");

		cy.click_custom_action_button("Get Fields");
		cy.get('[data-fieldname="web_form_fields"] .grid-row').should(
			"have.length.greaterThan",
			0
		);

		web_form_fields().then((collected) => {
			cy.save();
			web_form_fields().should("have.length", collected.length);
		});
	});

	it("Adds page two to a form that has only page one", () => {
		seed_web_form(SINGLE_PAGE_FIELDS);
		open_builder();

		// the strip stays hidden with one page, but the header still holds the add button
		cy.get(".tab-header .tabs .tab").should("not.be.visible");
		cy.get(".tab-header .tab-actions .new-tab-btn").should("be.visible").click();

		cy.get(".tab-header .tabs .tab").should("have.length", 2);
		cy.get(".tab-header .tabs .tab:last").should("contain.text", "Page 2");

		// a page needs a field, or get_updated_fields() prunes its empty section away
		cy.get(".tab-content.active .section-columns-container:first .column:first")
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

	it("Lays the stored rows out as pages", () => {
		seed_web_form();
		open_builder();

		// one Page Break row, but two pages — page one is implicit
		cy.get(".tab-header .tabs .tab").should("have.length", 2);
		cy.get(".tab-header .tabs .tab:first").should("contain.text", "Page 1");
		cy.get(".tab-content.active [data-fieldname='title']").should("exist");
		cy.get(".tab-content.active [data-fieldname='content']").should("not.exist");
	});

	it("Does not dirty the form by rendering", () => {
		open_builder();

		// the rebuild on mount trips the change watcher, but must not mark the record edited
		cy.get('[data-testid="page-status"]').should("not.contain.text", "Not Saved");
	});

	it("Writes the pages back without inventing a Page Break for page one", () => {
		open_builder();

		cy.get(".tab-content.active .form-section-container:first")
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

		cy.get(".tab-content.active .section-columns-container:first .column:first")
			.find(".add-new-field-btn button")
			.click();

		// a field already on the canvas is not on offer, an unplaced one is
		cy.get(".combo-box-options:visible .combo-box-option").should("not.contain.text", "Title");
		cy.get(".combo-box-options:visible .search-box > input").type("public{enter}");

		cy.get(".tab-content.active [data-fieldname='public']").should("exist");

		cy.click_doc_primary_button("Save");

		web_form_fields().then((fields) => {
			const placed = fields.filter((f) => f.fieldname === "public");
			expect(placed.length, "public appears once").to.eq(1);
			// the picker carries the source fieldtype over, not a chosen one
			expect(placed[0].fieldtype).to.eq("Check");
		});
	});

	it("Picks up rows removed from the Details tab", () => {
		seed_web_form();
		open_builder();

		cy.get(".tab-header .tabs .tab:last").click();
		cy.get(".tab-content.active [data-fieldname='content']").should("exist");

		cy.findByRole("tab", { name: "Details" }).click();
		cy.get('[data-fieldname="web_form_fields"] .grid-row')
			.contains("Content")
			.parents(".grid-row")
			.find(".grid-row-check")
			.click();
		cy.get('[data-fieldname="web_form_fields"] .grid-footer button')
			.contains("Delete")
			.click();

		cy.findByRole("tab", { name: "Form" }).click();
		cy.get(".tab-content [data-fieldname='content']").should("not.exist");
	});
});
