context("Folder Navigation", () => {
	before(() => {
		cy.visit("/login");
		cy.login();
		cy.visit("/app/file");
	});

	it("Adding Folders", () => {
		//Adding filter to go into the home folder
		cy.get(".filter-x-button").click();
		cy.click_filter_button();
		cy.get(".filter-action-buttons > .text-muted").findByText("+ Add a Filter").click();
		cy.get(".fieldname-select-area > .awesomplete > .form-control:last").type("Fol{enter}");
		cy.get(
			".filter-field > .form-group > .link-field > .awesomplete > .input-with-feedback"
		).type("Home{enter}");
		cy.get(".filter-action-buttons > div > .btn-primary").findByText("Apply Filters").click();

		//Adding folder (Test Folder)
		cy.click_menu_button("New Folder");
		cy.fill_field("value", "Test Folder");
		cy.click_modal_primary_button("Create");
	});

	it("Navigating the nested folders, checking if the URL formed is correct, checking if the added content in the child folder is correct", () => {
		//Navigating inside the Attachments folder
		cy.wait(500);
		cy.get('[title="Attachments"] > span').click();

		//To check if the URL formed after visiting the attachments folder is correct
		cy.location("pathname").should("eq", "/app/file/view/home/Attachments");
		cy.visit("/app/file/view/home/Attachments");

		//Adding folder inside the attachments folder
		cy.click_menu_button("New Folder");
		cy.fill_field("value", "Test Folder");
		cy.click_modal_primary_button("Create");

		//Navigating inside the added folder in the Attachments folder
		cy.wait(500);
		cy.get('[title="Test Folder"] > span').click();

		//To check if the URL is correct after visiting the Test Folder
		cy.location("pathname").should("eq", "/app/file/view/home/Attachments/Test%20Folder");
		cy.visit("/app/file/view/home/Attachments/Test%20Folder");

		//Adding a file inside the Test Folder
		cy.findByRole("button", { name: "Add File" }).eq(0).click({ force: true });
		cy.get(".file-uploader").findByText("Link").click();
		cy.get(".input-group > input.form-control:visible").as("upload_input");
		cy.get("@upload_input").type("https://wallpaperplay.com/walls/full/8/2/b/72402.jpg", {
			waitForAnimations: false,
			parseSpecialCharSequences: false,
			force: true,
			delay: 100,
		});
		cy.click_modal_primary_button("Upload");

		//To check if the added file is present in the Test Folder
		cy.visit("/app/file/view/home/Attachments");
		cy.wait(500);
		cy.get("span.level-item > a > span").should("contain", "Test Folder");
		cy.visit("/app/file/view/home/Attachments/Test%20Folder");

		cy.wait(500);
		cy.get(".list-row-container").eq(0).should("contain.text", "72402.jpg");
		cy.get(".list-row-checkbox").eq(0).click();

		cy.intercept({
			method: "POST",
			url: "api/method/frappe.desk.reportview.delete_items",
		}).as("file_deleted");

		//Deleting the added file from the Test folder
		cy.click_action_button("Delete");
		cy.click_modal_primary_button("Yes");
		cy.wait("@file_deleted");

		//Deleting the Test Folder
		cy.visit("/app/file/view/home/Attachments");
		cy.get(".list-row-checkbox").eq(0).click();
		cy.click_action_button("Delete");
		cy.click_modal_primary_button("Yes");
		cy.wait("@file_deleted");
	});

	it("Deleting Test Folder from the home", () => {
		//Deleting the Test Folder added in the home directory
		cy.visit("/app/file/view/home");
		cy.get(".level-left > .list-subject > .file-select >.list-row-checkbox")
			.eq(0)
			.click({ force: true, delay: 500 });
		cy.click_action_button("Delete");
		cy.click_modal_primary_button("Yes");
	});
});
