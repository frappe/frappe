import target_doctype from "../fixtures/layout_target_doctype";

const TARGET = target_doctype.name;
const SLUG = TARGET.toLowerCase().replace(/ /g, "-");

context("DocType Layout", () => {
	before(() => {
		cy.login("Administrator");
		cy.visit("/desk");
		cy.insert_doc("DocType", target_doctype, true);

		// Wipe any layouts from a previous run so field rows are deterministic
		cy.remove_doc("DocType Layout", "Compact", true);
		cy.remove_doc("DocType Layout", "Special", true);

		cy.insert_doc("DocType Layout", {
			title: "Compact",
			document_type: TARGET,
			fields: [
				{ fieldname: "data1", label: "Compact Data 1" },
				{ fieldname: "data2", hidden: 1 },
				{ fieldname: "is_special" },
				// `description` intentionally omitted so Sync Fields has a field to add
			],
		});

		cy.insert_doc("DocType Layout", {
			title: "Special",
			document_type: TARGET,
			condition: "doc.is_special == 1",
			fields: [
				{ fieldname: "data1" },
				{ fieldname: "data2" },
				{ fieldname: "is_special" },
				{ fieldname: "description", label: "Special Notes" },
			],
		});

		// Reload so frappe.boot.doctype_layouts includes the newly created layouts
		cy.visit("/desk");
	});

	it("DocType Layout form: Sync Fields populates rows and Form Builder renders", () => {
		cy.visit("/desk/doctype-layout/Compact");
		cy.get("body").should("have.attr", "data-ajax-state", "complete");

		// Field rows set via API in before() should already be present; `description`
		// was deliberately left out of the layout.
		cy.window()
			.its("cur_frm.doc.fields")
			.should((rows) => {
				const names = rows.map((r) => r.fieldname);
				expect(names).to.include.members(["data1", "data2", "is_special"]);
				expect(names).to.not.include("description");
			});

		// The missing `description` field is reported as added; wait for the
		// "Synced Fields" modal, then close it.
		cy.findByRole("button", { name: "Sync Fields" }).click({ force: true });
		cy.get(".modal:visible").should("contain.text", "Synced Fields");
		cy.hide_dialog();

		// frm.dirty() + frm.refresh_field() cause an async re-render; wait for the
		// "Not Saved" pill to appear before querying the tab.
		cy.get(".title-area .indicator-pill").should("contain.text", "Not Saved");

		// Wait for the form builder bundle to load and initialize before clicking the tab.
		// cy.window().its("frappe").its("layout_builder").should("exist");
		cy.findByRole("tab", { name: "Parent Layout" }).click();
		cy.get(".form-builder-container").should("exist");
	});

	it("Condition auto-switches the layout after a matching value is saved", () => {
		cy.visit(`/desk/${SLUG}/new`);
		cy.get("body").should("have.attr", "data-ajax-state", "complete");

		// Condition unmet — no layout
		cy.get(".layout-indicator").should("not.exist");

		cy.fill_field("data1", "auto-switch", "Data");
		cy.get("[data-fieldname='is_special'] label").click({ force: true });
		cy.click_doc_primary_button("Save");

		cy.get(".layout-indicator").should("contain.text", "Special");
		cy.location("search").should("include", "layout=Special");
		cy.get("[data-fieldname='description'] .clearfix label").should(
			"contain.text",
			"Special Notes"
		);
	});
});
