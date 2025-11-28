context("FileUploader", () => {
	before(() => {
		cy.login();
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
		const test_user = "test_restricted_uploader@example.com";

		before(() => {
			// Create a test user
			cy.call("frappe.tests.ui_test_helpers.create_test_user", {
				username: test_user,
			});
			// Remove System Manager role to make them non-System Manager
			cy.remove_role(test_user, "System Manager");
		});

		it("should hide Private checkbox and toggle button when setting is enabled for non-System Manager", () => {
			// Enable the setting
			cy.call("frappe.db.set_single_value", {
				doctype: "System Settings",
				field: "only_allow_system_managers_to_upload_public_files",
				value: 1,
			});

			// Login as non-System Manager
			cy.login(test_user);
			cy.visit("/desk");
			cy.wait(2000);

			// Open upload dialog
			open_upload_dialog();

			// Verify Private checkbox is hidden
			cy.get_open_dialog()
				.find("label.frappe-checkbox")
				.contains("Private")
				.should("not.exist");

			// Verify toggle button is hidden (secondary action in dialog footer)
			cy.get_open_dialog()
				.find(".modal-footer")
				.find('button[data-label*="Set all"]')
				.should("not.exist");

			cy.hide_dialog();
		});

		it("should show Private checkbox and toggle button when setting is enabled for System Manager", () => {
			// Enable the setting
			cy.call("frappe.db.set_single_value", {
				doctype: "System Settings",
				field: "only_allow_system_managers_to_upload_public_files",
				value: 1,
			});

			// Login as Administrator (System Manager)
			cy.login("Administrator");
			cy.visit("/desk");
			cy.wait(2000);

			// Open upload dialog
			open_upload_dialog();

			// Verify Private checkbox is visible
			cy.get_open_dialog().find(".frappe-checkbox").contains("Private").should("be.visible");

			// Verify toggle button is visible (secondary action in dialog footer)
			cy.get_open_dialog()
				.find(".modal-footer")
				.find('button:contains("Set all private"), button:contains("Set all public")')
				.should("be.visible");

			cy.hide_dialog();
		});

		it("should show Private checkbox and toggle button when setting is disabled", () => {
			// Disable the setting
			cy.call("frappe.db.set_single_value", {
				doctype: "System Settings",
				field: "only_allow_system_managers_to_upload_public_files",
				value: 0,
			});

			// Login as non-System Manager
			cy.login(test_user);
			cy.visit("/desk");
			cy.wait(2000);

			// Open upload dialog
			open_upload_dialog();

			// Verify Private checkbox is visible
			cy.get_open_dialog().find(".frappe-checkbox").contains("Private").should("be.visible");

			// Verify toggle button is visible (secondary action in dialog footer)
			cy.get_open_dialog()
				.find(".modal-footer")
				.find('button:contains("Set all private"), button:contains("Set all public")')
				.should("be.visible");

			cy.hide_dialog();
		});
	});
});
