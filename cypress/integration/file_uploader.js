context("FileUploader", () => {
	before(() => {
		cy.login("Administrator", Cypress.env("adminPassword") || "admin");
	});

	beforeEach(() => {
		cy.visit("/desk");
		cy.wait(2000); // workspace can load async and clear active dialog
	});

	function open_upload_dialog() {
		cy.window()
			.its("frappe")
			.then((frappe) => {
				new frappe.ui.FileUploader();
			});
		cy.wait(500);
	}

	it("upload dialog api works", () => {
		open_upload_dialog();
		cy.get_open_dialog().should("contain", "Drag and drop files");
		cy.hide_dialog();
	});

	it("should accept dropped files", () => {
		open_upload_dialog();

		cy.get_open_dialog()
			.find(".file-upload-area")
			.selectFile("cypress/fixtures/example.json", {
				action: "drag-drop",
			});

		cy.get_open_dialog().find(".file-name").should("contain", "example.json");
		cy.intercept("POST", "/api/method/upload_file").as("upload_file");
		cy.get_open_dialog().findByRole("button", { name: "Upload" }).click();
		cy.wait("@upload_file").its("response.statusCode").should("eq", 200);
		cy.get(".modal:visible").should("not.exist");
	});

	it("should accept uploaded files", () => {
		open_upload_dialog();

		cy.get_open_dialog().findByRole("button", { name: "Library" }).click();
		cy.findByPlaceholderText("Search by filename or extension").type("example.json");
		cy.get_open_dialog().findAllByText("example.json").first().click();
		cy.intercept("POST", "/api/method/upload_file").as("upload_file");
		cy.get_open_dialog().findByRole("button", { name: "Upload" }).click();
		cy.wait("@upload_file")
			.its("response.body.message")
			.should("have.property", "file_name", "example.json");
		cy.get(".modal:visible").should("not.exist");
	});

	describe("Public file upload restriction", () => {
		const test_user = "test_file_uploader@example.com";
		const test_password = "test_password";

		before(() => {
			// Create test user without System Manager role
			cy.call("frappe.tests.ui_test_helpers.create_test_user", {
				username: test_user,
			});
			cy.remove_role(test_user, "System Manager");
			// Set password for test user
			cy.set_value("User", test_user, {
				new_password: test_password,
			});
		});

		after(() => {
			// Clean up test user
			cy.login("Administrator", Cypress.env("adminPassword") || "admin");
			cy.visit("/desk");
			cy.wait(1000);
			cy.remove_doc("User", test_user, true); // true = ignore_missing
		});

		it("should show checkbox and toggle when setting is disabled for System Manager", () => {
			cy.login("Administrator", Cypress.env("adminPassword") || "admin");
			cy.visit("/desk");
			cy.wait(1000);

			// Disable the setting
			cy.set_value("System Settings", "System Settings", {
				only_allow_system_managers_to_upload_public_files: 0,
			});
			// Update sysdefaults in window to avoid reload
			cy.window()
				.its("frappe")
				.then((frappe) => {
					frappe.boot.sysdefaults.only_allow_system_managers_to_upload_public_files = 0;
				});
			cy.visit("/desk");
			cy.wait(2000);

			open_upload_dialog();

			// Add a file to the dialog
			cy.get_open_dialog()
				.find(".file-upload-area")
				.selectFile("cypress/fixtures/example.json", {
					action: "drag-drop",
				});

			// Wait for file preview to render
			cy.get_open_dialog().find(".file-preview").should("exist");

			// Checkbox should be visible and enabled
			cy.get_open_dialog().find("#uploader-private-checkbox").should("be.visible");
			cy.get_open_dialog()
				.find("#uploader-private-checkbox input")
				.should("not.be.disabled");

			// Toggle button should be visible (secondary action button)
			cy.get_open_dialog()
				.find(".modal-footer .btn-secondary")
				.should("be.visible")
				.and("contain", "Set all");

			cy.hide_dialog();
		});

		it("should show checkbox and toggle when setting is disabled for non-System Manager", () => {
			cy.login("Administrator", Cypress.env("adminPassword") || "admin");
			cy.visit("/desk");
			cy.wait(1000);

			// Disable the setting
			cy.set_value("System Settings", "System Settings", {
				only_allow_system_managers_to_upload_public_files: 0,
			});
			cy.visit("/desk");
			cy.wait(1000);

			// Login as non-System Manager
			cy.login(test_user, test_password);
			cy.visit("/desk");
			cy.wait(2000);
			// Update sysdefaults in window
			cy.window()
				.its("frappe")
				.then((frappe) => {
					frappe.boot.sysdefaults.only_allow_system_managers_to_upload_public_files = 0;
				});

			open_upload_dialog();

			// Add a file to the dialog
			cy.get_open_dialog()
				.find(".file-upload-area")
				.selectFile("cypress/fixtures/example.json", {
					action: "drag-drop",
				});

			// Wait for file preview to render
			cy.get_open_dialog().find(".file-preview").should("exist");

			// Checkbox should be visible and enabled
			cy.get_open_dialog().find("#uploader-private-checkbox").should("be.visible");
			cy.get_open_dialog()
				.find("#uploader-private-checkbox input")
				.should("not.be.disabled");

			// Toggle button should be visible (secondary action button)
			cy.get_open_dialog()
				.find(".modal-footer .btn-secondary")
				.should("be.visible")
				.and("contain", "Set all");

			cy.hide_dialog();
		});

		it("should show checkbox and toggle when setting is enabled for System Manager", () => {
			cy.login("Administrator", Cypress.env("adminPassword") || "admin");
			cy.visit("/desk");
			cy.wait(1000);

			// Enable the setting
			cy.set_value("System Settings", "System Settings", {
				only_allow_system_managers_to_upload_public_files: 1,
			});
			// Update sysdefaults in window to avoid reload
			cy.window()
				.its("frappe")
				.then((frappe) => {
					frappe.boot.sysdefaults.only_allow_system_managers_to_upload_public_files = 1;
				});
			cy.visit("/desk");
			cy.wait(2000);

			open_upload_dialog();

			// Add a file to the dialog
			cy.get_open_dialog()
				.find(".file-upload-area")
				.selectFile("cypress/fixtures/example.json", {
					action: "drag-drop",
				});

			// Wait for file preview to render
			cy.get_open_dialog().find(".file-preview").should("exist");

			// Checkbox should be visible and enabled
			cy.get_open_dialog().find("#uploader-private-checkbox").should("be.visible");
			cy.get_open_dialog()
				.find("#uploader-private-checkbox input")
				.should("not.be.disabled");

			// Toggle button should be visible (secondary action button)
			cy.get_open_dialog()
				.find(".modal-footer .btn-secondary")
				.should("be.visible")
				.and("contain", "Set all");

			cy.hide_dialog();
		});

		it("should show disabled checkbox and hide toggle when setting is enabled for non-System Manager", () => {
			cy.login("Administrator", Cypress.env("adminPassword") || "admin");
			cy.visit("/desk");
			cy.wait(1000);

			// Enable the setting
			cy.set_value("System Settings", "System Settings", {
				only_allow_system_managers_to_upload_public_files: 1,
			});
			cy.visit("/desk");
			cy.wait(1000);

			// Login as non-System Manager
			cy.login(test_user, test_password);
			cy.visit("/desk");
			cy.wait(2000);
			// Update sysdefaults in window
			cy.window()
				.its("frappe")
				.then((frappe) => {
					frappe.boot.sysdefaults.only_allow_system_managers_to_upload_public_files = 1;
				});

			open_upload_dialog();

			// Add a file to the dialog
			cy.get_open_dialog()
				.find(".file-upload-area")
				.selectFile("cypress/fixtures/example.json", {
					action: "drag-drop",
				});

			// Wait for file preview to render
			cy.get_open_dialog().find(".file-preview").should("exist");

			// Checkbox should be visible but disabled
			cy.get_open_dialog().find("#uploader-private-checkbox").should("be.visible");
			cy.get_open_dialog().find("#uploader-private-checkbox input").should("be.disabled");

			// Toggle button should not be visible (secondary action button should be hidden)
			cy.get_open_dialog().find(".modal-footer .btn-secondary").should("not.be.visible");

			cy.hide_dialog();
		});
	});
});
