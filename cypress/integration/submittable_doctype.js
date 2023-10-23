import custom_submittable_doctype from "../fixtures/custom_submittable_doctype";

context("Submittable doctype", () => {
	before(() => {
		cy.visit("/login");
		cy.login();

		// Create custom submittable doctype
		cy.visit("/app/doctype");
		cy.insert_doc("DocType", custom_submittable_doctype, true);
	});

	it("Submittable doc can be created via Quick Entry form", () => {
		cy.visit("/app/custom-submittable-doctype");
		cy.click_listview_primary_button("Add Custom Submittable DocType");

		// Add a new entry via Quick Entry Form.
		cy.fill_field("title", "Test");
		cy.click_modal_primary_button("Save");
		cy.click_modal_primary_button("Submit");

		// Find the new document and cancel it.
		cy.visit("/app/custom-submittable-doctype");
		cy.click_listview_row_item(0);
		cy.get('[id="page-Custom Submittable DocType"] .page-actions')
			.findByRole("button", { name: "Cancel" })
			.click();
		cy.get_open_dialog().findByRole("button", { name: "Yes" }).click();

		// Now delete the document.
		cy.visit("/app/custom-submittable-doctype");
		cy.select_listview_row_checkbox(0);
		cy.get(".page-actions").findByRole("button", { name: "Actions" }).click();
		cy.get('.page-actions .actions-btn-group [data-label="Delete"]').click();
		cy.click_modal_primary_button("Yes");
	});

	it("Submittable doc can be created via full form", () => {
		cy.visit("/app/custom-submittable-doctype");
		cy.click_listview_primary_button("Add Custom Submittable DocType");

		// Dismiss Quick Entry and create a new document via full form.
		cy.click_modal_custom_button("Edit Full Form");
		cy.fill_field("title", "Test");
		cy.click_doc_primary_button("Save");
		cy.click_doc_primary_button("Submit");

		cy.visit("/app/custom-submittable-doctype");
		cy.click_listview_row_item(0);
	});
});
