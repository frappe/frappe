import custom_submittable_doctype from "../fixtures/custom_submittable_doctype";

context("Timeline", () => {
	before(() => {
		cy.visit("/login");
		cy.login();
	});

	it("Adding new ToDo, adding new comment, verifying comment addition & deletion and deleting ToDo", () => {
		//Adding new ToDo
		cy.new_form("ToDo");
		cy.get('[data-fieldname="description"] .ql-editor.ql-blank')
			.type("Test ToDo", { force: true })
			.wait(200);
		cy.get(".page-head .page-actions").findByRole("button", { name: "Save" }).click();

		cy.go_to_list("ToDo");
		cy.clear_filters();
		cy.click_listview_row_item(0);

		//To check if the comment box is initially empty and tying some text into it
		cy.get('[data-fieldname="comment"] .ql-editor')
			.should("contain", "")
			.type("Testing Timeline");

		//Adding new comment
		cy.get(".comment-box").findByRole("button", { name: "Comment" }).click();

		//To check if the commented text is visible in the timeline content
		cy.get(".timeline-content").should("contain", "Testing Timeline");

		//Editing comment
		cy.click_timeline_action_btn("Edit");
		cy.get('.timeline-content [data-fieldname="comment"] .ql-editor').first().type(" 123");
		cy.click_timeline_action_btn("Save");

		//To check if the edited comment text is visible in timeline content
		cy.get(".timeline-content").should("contain", "Testing Timeline 123");

		//Discarding comment
		cy.click_timeline_action_btn("Edit");
		cy.click_timeline_action_btn("Dismiss");

		//To check if after discarding the timeline content is same as previous
		cy.get(".timeline-content").should("contain", "Testing Timeline 123");

		//Deleting the added comment
		cy.get(".timeline-message-box .more-actions > .action-btn").click(); //Menu button in timeline item
		cy.get(".timeline-message-box .more-actions .dropdown-item")
			.contains("Delete")
			.click({ force: true });
		cy.get_open_dialog().findByRole("button", { name: "Yes" }).click({ force: true });

		cy.get(".timeline-content").should("not.contain", "Testing Timeline 123");
	});

	it("Timeline should have submit and cancel activity information", () => {
		cy.visit("/app/doctype");

		//Creating custom doctype
		cy.insert_doc("DocType", custom_submittable_doctype, true);

		cy.visit("/app/custom-submittable-doctype");
		cy.click_listview_primary_button("Add Custom Submittable DocType");

		//Adding a new entry for the created custom doctype
		cy.fill_field("title", "Test");
		cy.click_modal_primary_button("Save");
		cy.click_modal_primary_button("Submit");

		cy.visit("/app/custom-submittable-doctype");
		cy.click_listview_row_item(0);

		//To check if the submission of the documemt is visible in the timeline content
		cy.get(".timeline-content").should("contain", "Frappe submitted this document");
		cy.get('[id="page-Custom Submittable DocType"] .page-actions')
			.findByRole("button", { name: "Cancel" })
			.click();
		cy.get_open_dialog().findByRole("button", { name: "Yes" }).click();

		//To check if the cancellation of the documemt is visible in the timeline content
		cy.get(".timeline-content").should("contain", "Frappe cancelled this document");

		//Deleting the document
		cy.visit("/app/custom-submittable-doctype");
		cy.select_listview_row_checkbox(0);
		cy.get(".page-actions").findByRole("button", { name: "Actions" }).click();
		cy.get('.page-actions .actions-btn-group [data-label="Delete"]').click();
		cy.click_modal_primary_button("Yes");
	});
});
