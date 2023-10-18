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

		//Clicking on "Link" button to attach a file using the "Link" button
		cy.findByRole("button", { name: "Link" }).click();
		cy.findByPlaceholderText("Attach a web link").type(
			"https://wallpaperplay.com/walls/full/8/2/b/72402.jpg",
			{ force: true }
		);

		//Clicking on the Upload button to upload the file
		cy.intercept("POST", "/api/method/upload_file").as("upload_image");
		cy.get(".modal-footer").findByRole("button", { name: "Upload" }).click({ delay: 500 });
		cy.wait("@upload_image");
		cy.findByRole("button", { name: "Save" }).click();

		//Navigating to the new form for the newly created doctype to check Library button
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

		//Deleting both docs
		cy.go_to_list("Test Attach Control");
		cy.get(".list-row-checkbox").eq(0).click();
		cy.get(".list-row-checkbox").eq(1).click();
		cy.get(".actions-btn-group > .btn").contains("Actions").click();
		cy.get('.actions-btn-group > .dropdown-menu [data-label="Delete"]').click();
		cy.click_modal_primary_button("Yes");
	});

	it('Checking that "Camera" button in the "Attach" fieldtype does show if camera is available', () => {
		//Navigating to the new form for the newly created doctype
		let doctype = "Test Attach Control";
		let dt_in_route = doctype.toLowerCase().replace(/ /g, "-");
		cy.visit(`/app/${dt_in_route}/new`, {
			onBeforeLoad(win) {
				// Mock "window.navigator.mediaDevices" property
				// to return mock mediaDevices object
				win.navigator.mediaDevices = {
					ondevicechange: null,
				};
			},
		});
		cy.get("body").should(($body) => {
			const dataRoute = $body.attr("data-route");
			expect(dataRoute).to.match(new RegExp(`^Form/${doctype}/new-${dt_in_route}-`));
		});
		cy.get("body").should("have.attr", "data-ajax-state", "complete");

		//Clicking on the attach button which is displayed as part of creating a doctype with "Attach" fieldtype
		cy.findByRole("button", { name: "Attach" }).click();

		//Clicking on "Camera" button
		cy.findByRole("button", { name: "Camera" }).should("exist");
	});

	it('Checking that "Camera" button in the "Attach" fieldtype does not show if no camera is available', () => {
		//Navigating to the new form for the newly created doctype
		let doctype = "Test Attach Control";
		let dt_in_route = doctype.toLowerCase().replace(/ /g, "-");
		cy.visit(`/app/${dt_in_route}/new`, {
			onBeforeLoad(win) {
				// Delete "window.navigator.mediaDevices" property
				delete win.navigator.mediaDevices;
			},
		});
		cy.get("body").should(($body) => {
			const dataRoute = $body.attr("data-route");
			expect(dataRoute).to.match(new RegExp(`^Form/${doctype}/new-${dt_in_route}-`));
		});
		cy.get("body").should("have.attr", "data-ajax-state", "complete");

		//Clicking on the attach button which is displayed as part of creating a doctype with "Attach" fieldtype
		cy.findByRole("button", { name: "Attach" }).click();

		//Clicking on "Camera" button
		cy.findByRole("button", { name: "Camera" }).should("not.exist");
	});
});
context("Attach Control with Failed Document Save", () => {
	before(() => {
		cy.login();
		cy.visit("/app/doctype");
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.xcall("frappe.tests.ui_test_helpers.create_doctype", {
					name: "Test Mandatory Attach Control",
					fields: [
						{
							label: "Attach File or Image",
							fieldname: "attach",
							fieldtype: "Attach",
							in_list_view: 1,
						},
						{
							label: "Mandatory Text Field",
							fieldname: "text_field",
							fieldtype: "Text Editor",
							in_list_view: 1,
							reqd: 1,
						},
					],
				});
			});
	});
	let temp_name = "";
	let docname = "";
	it("Attaching a file on an unsaved document", () => {
		//Navigating to the new form for the newly created doctype
		cy.new_form("Test Mandatory Attach Control");
		cy.get("body").should(($body) => {
			temp_name = $body.attr("data-route").split("/")[2];
		});

		//Clicking on the attach button which is displayed as part of creating a doctype with "Attach" fieldtype
		cy.findByRole("button", { name: "Attach" }).click();

		//Clicking on "Link" button to attach a file using the "Link" button
		cy.findByRole("button", { name: "Link" }).click();
		cy.findByPlaceholderText("Attach a web link").type(
			"https://wallpaperplay.com/walls/full/8/2/b/72402.jpg",
			{ force: true }
		);

		//Clicking on the Upload button to upload the file
		cy.intercept("POST", "/api/method/upload_file").as("upload_image");
		cy.get(".modal-footer").findByRole("button", { name: "Upload" }).click({ delay: 500 });
		cy.wait("@upload_image");
		cy.get(".msgprint-dialog .modal-title").contains("Missing Fields").should("be.visible");
		cy.hide_dialog();
		cy.fill_field("text_field", "Random value", "Text Editor").wait(500);
		cy.findByRole("button", { name: "Save" }).click().wait(500);

		//Checking if the URL of the attached image is getting displayed in the field of the newly created doctype
		cy.get(".attached-file > .ellipsis > .attached-file-link")
			.should("have.attr", "href")
			.and("equal", "https://wallpaperplay.com/walls/full/8/2/b/72402.jpg");

		cy.get(".title-text").then(($value) => {
			docname = $value.text();
		});
	});

	it("Check if file was uploaded correctly", () => {
		cy.go_to_list("File");
		cy.open_list_filter();
		cy.get(".fieldname-select-area .form-control")
			.click()
			.type("Attached To Name{enter}")
			.blur()
			.wait(500);
		cy.get('input[data-fieldname="attached_to_name"]').click().type(docname).blur();
		cy.get(".filter-popover .apply-filters").click({ force: true });
		cy.get("header .level-right .list-count").should("contain.text", "1 of 1");
	});

	it("Check if file exists with temporary name", () => {
		cy.open_list_filter();
		cy.get('input[data-fieldname="attached_to_name"]').click().clear().type(temp_name).blur();
		cy.get(".filter-popover .apply-filters").click({ force: true });
		cy.get(".frappe-list > .no-result").should("be.visible");
	});
});
