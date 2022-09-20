context("Attach Control", () => {
	before(() => {
		cy.login();
		cy.visit("/app/doctype");
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.xcall("frappe.tests.ui_test_helpers.create_doctype", {
					name: "Test Attach Control",
					fields: [
						{
							label: "Attach File or Image",
							fieldname: "attach",
							fieldtype: "Attach",
							in_list_view: 1,
						},
					],
				});
			});
	});
	it('Checking functionality for "Link" button in the "Attach" fieldtype', () => {
		//Navigating to the new form for the newly created doctype
		cy.new_form("Test Attach Control");

		//Clicking on the attach button which is displayed as part of creating a doctype with "Attach" fieldtype
		cy.findByRole("button", { name: "Attach" }).click();

		//Clicking on "Link" button to attach a file using the "Link" button
		cy.findByRole("button", { name: "Link" }).click();
		cy.findByPlaceholderText("Attach a web link").type(
			"https://wallpaperplay.com/walls/full/8/2/b/72402.jpg"
		);

		//Clicking on the Upload button to upload the file
		cy.intercept("POST", "/api/method/upload_file").as("upload_image");
		cy.get(".modal-footer").findByRole("button", { name: "Upload" }).click({ delay: 500 });
		cy.wait("@upload_image");
		cy.findByRole("button", { name: "Save" }).click();

		//Checking if the URL of the attached image is getting displayed in the field of the newly created doctype
		cy.get(".attached-file > .ellipsis > .attached-file-link")
			.should("have.attr", "href")
			.and("equal", "https://wallpaperplay.com/walls/full/8/2/b/72402.jpg");

		//Clicking on the "Clear" button
		cy.get('[data-action="clear_attachment"]').click();

		//Checking if clicking on the clear button clears the field of the doctype form and again displays the attach button
		cy.get(".control-input > .btn-sm").should("contain", "Attach");

		//Deleting the doc
		cy.go_to_list("Test Attach Control");
		cy.get(".list-row-checkbox").eq(0).click();
		cy.get(".actions-btn-group > .btn").contains("Actions").click();
		cy.get('.actions-btn-group > .dropdown-menu [data-label="Delete"]').click();
		cy.click_modal_primary_button("Yes");
	});

	it('Checking functionality for "Library" button in the "Attach" fieldtype', () => {
		//Navigating to the new form for the newly created doctype
		cy.new_form("Test Attach Control");

		//Clicking on the attach button which is displayed as part of creating a doctype with "Attach" fieldtype
		cy.findByRole("button", { name: "Attach" }).click();

		//Clicking on "Library" button to attach a file using the "Library" button
		cy.findByRole("button", { name: "Library" }).click();
		cy.contains("72402.jpg").click();

		//Clicking on the Upload button to upload the file
		cy.intercept("POST", "/api/method/upload_file").as("upload_image");
		cy.get(".modal-footer").findByRole("button", { name: "Upload" }).click({ delay: 500 });
		cy.wait("@upload_image");
		cy.findByRole("button", { name: "Save" }).click();

		//Checking if the URL of the attached image is getting displayed in the field of the newly created doctype
		cy.get(".attached-file > .ellipsis > .attached-file-link")
			.should("have.attr", "href")
			.and("equal", "https://wallpaperplay.com/walls/full/8/2/b/72402.jpg");

		//Clicking on the "Clear" button
		cy.get('[data-action="clear_attachment"]').click();

		//Checking if clicking on the clear button clears the field of the doctype form and again displays the attach button
		cy.get(".control-input > .btn-sm").should("contain", "Attach");

		//Deleting the doc
		cy.go_to_list("Test Attach Control");
		cy.get(".list-row-checkbox").eq(0).click();
		cy.get(".actions-btn-group > .btn").contains("Actions").click();
		cy.get('.actions-btn-group > .dropdown-menu [data-label="Delete"]').click();
		cy.click_modal_primary_button("Yes");
	});
});
