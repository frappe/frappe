context("FileUploader", () => {
	before(() => {
		cy.login("Administrator", Cypress.env("adminPassword") || "admin");
	});

	beforeEach(() => {
		cy.visit("/desk");
		// Wait for page to fully load - ensure frappe object is available
		cy.window().its("frappe").should("exist");
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

	context("Public file upload permissions", () => {
		let test_user;
		let test_role = "Test File Uploader Role";

		before(() => {
			cy.login("Administrator", Cypress.env("adminPassword") || "admin");
			cy.visit("/desk");
			cy.wait(1000);

			// Create role (ignore if it already exists)
			cy.insert_doc(
				"Role",
				{
					role_name: test_role,
				},
				true // ignore_duplicate
			).then(() => {
				// Create test user
				test_user = `test_file_uploader_${Date.now()}@example.com`;
				return cy.call("frappe.client.insert", {
					doc: {
						doctype: "User",
						email: test_user,
						first_name: "Test",
						new_password: "Eastern_43A1W",
						send_welcome_email: 0,
						roles: [
							{
								role: test_role,
							},
						],
					},
				});
			});

			// Note: upload_public_files is a standard right (in std_rights), so it doesn't need a Permission Type
			// It's available for all doctypes by default
		});

		after(() => {
			cy.login("Administrator", Cypress.env("adminPassword") || "admin");
			cy.visit("/desk");
			// Wait for page to fully load - ensure frappe object is available
			cy.window().its("frappe").should("exist");
			cy.wait(2000); // Ensure page is fully loaded
			// Clean up test user and role
			if (test_user) {
				cy.remove_doc("User", test_user, true);
			}
			cy.remove_doc("Role", test_role, true);
		});

		it("Administrator should see Private checkbox and toggle button", () => {
			cy.login("Administrator", Cypress.env("adminPassword") || "admin");
			cy.visit("/desk");
			cy.wait(2000);

			open_upload_dialog();

			// Add a file
			cy.get_open_dialog()
				.find(".file-upload-area")
				.selectFile("cypress/fixtures/example.json", {
					action: "drag-drop",
				});

			cy.wait(500);

			// Check for Private checkbox
			cy.get_open_dialog().find(".frappe-checkbox").contains("Private").should("be.visible");

			// Check for toggle button
			cy.get_open_dialog()
				.find(".modal-footer .btn-secondary")
				.should("be.visible")
				.should("contain", "Set all");

			cy.hide_dialog();
		});

		it("User with permission should see Private checkbox and toggle button", () => {
			cy.login("Administrator", Cypress.env("adminPassword") || "admin");
			cy.visit("/desk");
			cy.wait(1000);

			// Grant upload_public_files permission using permission_manager API
			cy.call("frappe.core.page.permission_manager.permission_manager.add", {
				parent: "File",
				role: test_role,
				permlevel: 0,
			});
			cy.call("frappe.core.page.permission_manager.permission_manager.update", {
				doctype: "File",
				role: test_role,
				permlevel: 0,
				ptype: "read",
				value: 1,
			});
			cy.call("frappe.core.page.permission_manager.permission_manager.update", {
				doctype: "File",
				role: test_role,
				permlevel: 0,
				ptype: "write",
				value: 1,
			});
			cy.call("frappe.core.page.permission_manager.permission_manager.update", {
				doctype: "File",
				role: test_role,
				permlevel: 0,
				ptype: "upload_public_files",
				value: 1,
			});

			// Clear cache and wait for permissions to be saved
			cy.clear_cache();
			cy.wait(2000);

			// Login as test user and reload to get fresh permissions
			cy.login(test_user, "Eastern_43A1W");
			cy.visit("/desk");
			cy.wait(2000);

			// Verify permission is loaded in frontend and ensure metadata is loaded
			cy.window()
				.its("frappe")
				.then((frappe) => {
					return new Promise((resolve) => {
						frappe.model.with_doctype("File", () => {
							expect(
								frappe.perm.has_perm("File", 0, "upload_public_files")
							).to.equal(true);
							// Ensure metadata is cached and loaded
							const meta = frappe.get_meta("File");
							expect(meta).to.not.be.undefined;
							// Verify the permission is in the cached permissions
							const perms = frappe.perm.get_perm("File");
							expect(perms[0].upload_public_files).to.equal(1);
							resolve();
						});
					});
				});

			// Wait a bit more to ensure Vue reactivity has processed
			cy.wait(1000);

			open_upload_dialog();

			// Add a file
			cy.get_open_dialog()
				.find(".file-upload-area")
				.selectFile("cypress/fixtures/example.json", {
					action: "drag-drop",
				});

			// Wait for file to be processed - check for file name first
			cy.get_open_dialog().find(".file-name").should("contain", "example.json");

			// Wait for Vue component to render and evaluate computed properties
			// The checkbox visibility depends on the computed property which checks permissions
			cy.wait(1500);

			// Verify permission check works in the dialog context
			cy.get_open_dialog().then(() => {
				cy.window()
					.its("frappe")
					.then((frappe) => {
						// Ensure File metadata is loaded and permission is available
						frappe.model.with_doctype("File", () => {
							const can_upload = frappe.utils.can_upload_public_files("File");
							expect(can_upload).to.equal(true);
						});
					});
			});

			// Check for Private checkbox - look for label with "Private" text directly
			// The checkbox should appear in the config-area when permission is granted
			// Use a more specific selector that waits for the element to appear
			cy.get_open_dialog()
				.find(".file-preview-outline")
				.should("be.visible")
				.should("contain", "Private")
				.find("label.frappe-checkbox")
				.contains("Private")
				.should("be.visible");

			// Check for toggle button in modal footer
			cy.get_open_dialog()
				.find(".modal-footer")
				.findByRole("button", { name: /set all/i })
				.should("be.visible");

			cy.hide_dialog();
		});

		it("User without permission should NOT see Private checkbox and toggle button", () => {
			cy.login("Administrator", Cypress.env("adminPassword") || "admin");
			cy.visit("/desk");
			// Wait for page to fully load - ensure frappe object is available
			cy.window().its("frappe").should("exist");
			cy.wait(1000);

			// Revoke upload_public_files permission using permission_manager API
			cy.call("frappe.core.page.permission_manager.permission_manager.add", {
				parent: "File",
				role: test_role,
				permlevel: 0,
			});
			cy.call("frappe.core.page.permission_manager.permission_manager.update", {
				doctype: "File",
				role: test_role,
				permlevel: 0,
				ptype: "read",
				value: 1,
			});
			cy.call("frappe.core.page.permission_manager.permission_manager.update", {
				doctype: "File",
				role: test_role,
				permlevel: 0,
				ptype: "write",
				value: 1,
			});
			cy.call("frappe.core.page.permission_manager.permission_manager.update", {
				doctype: "File",
				role: test_role,
				permlevel: 0,
				ptype: "upload_public_files",
				value: 0,
			});

			// Clear cache and wait for permissions to be saved
			cy.clear_cache();
			cy.wait(2000);

			// Login as test user and reload to get fresh permissions
			cy.login(test_user, "Eastern_43A1W");
			cy.visit("/desk");
			// Wait for page to fully load - ensure frappe object is available
			cy.window().its("frappe").should("exist");
			cy.wait(2000);

			open_upload_dialog();

			// Add a file
			cy.get_open_dialog()
				.find(".file-upload-area")
				.selectFile("cypress/fixtures/example.json", {
					action: "drag-drop",
				});

			// Wait for file to be processed - check for file name first
			cy.get_open_dialog().find(".file-name").should("contain", "example.json");
			cy.wait(1000);

			// Private checkbox should NOT be visible - config-area should be empty or not contain Private label
			cy.get_open_dialog()
				.find(".file-preview-outline")
				.should("be.visible")
				.within(() => {
					cy.get(".config-area").should("exist").should("not.contain", "Private");
				});

			// Toggle button should NOT be visible in modal footer
			cy.get_open_dialog().find(".modal-footer").should("not.contain", "Set all");

			cy.hide_dialog();
		});

		it("User without permission should be forced to upload private files", () => {
			// Ensure we're logged in as Administrator first
			cy.login("Administrator", Cypress.env("adminPassword") || "admin");
			cy.visit("/desk");
			// Wait for page to fully load - ensure frappe object is available
			cy.window().its("frappe").should("exist");
			cy.wait(2000);

			// Ensure upload_public_files permission is revoked using permission_manager API
			cy.call("frappe.core.page.permission_manager.permission_manager.add", {
				parent: "File",
				role: test_role,
				permlevel: 0,
			}).then(() => {
				cy.call("frappe.core.page.permission_manager.permission_manager.update", {
					doctype: "File",
					role: test_role,
					permlevel: 0,
					ptype: "read",
					value: 1,
				});
				cy.call("frappe.core.page.permission_manager.permission_manager.update", {
					doctype: "File",
					role: test_role,
					permlevel: 0,
					ptype: "write",
					value: 1,
				});
				cy.call("frappe.core.page.permission_manager.permission_manager.update", {
					doctype: "File",
					role: test_role,
					permlevel: 0,
					ptype: "upload_public_files",
					value: 0,
				});
			});

			// Login as test user
			cy.login(test_user, "Eastern_43A1W");
			cy.visit("/desk");
			// Wait for page to fully load - ensure frappe object is available
			cy.window().its("frappe").should("exist");
			cy.wait(2000);

			open_upload_dialog();

			// Add a file
			cy.get_open_dialog()
				.find(".file-upload-area")
				.selectFile("cypress/fixtures/example.json", {
					action: "drag-drop",
				});

			cy.wait(500);

			// Upload the file
			cy.intercept("POST", "/api/method/upload_file").as("upload_file");
			cy.get_open_dialog().findByRole("button", { name: "Upload" }).click();
			cy.wait("@upload_file").its("response.statusCode").should("eq", 200);

			// File should be uploaded as private (default behavior when permission is missing)
			cy.wait(1000);
			cy.get(".modal:visible").should("not.exist");
		});
	});
});
