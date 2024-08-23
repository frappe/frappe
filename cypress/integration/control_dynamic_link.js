context("Dynamic Link", () => {
	before(() => {
		cy.login();
		cy.visit("/app/doctype");
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.xcall("frappe.tests.ui_test_helpers.create_doctype", {
					name: "Test Dynamic Link",
					fields: [
						{
							label: "Document Type",
							fieldname: "doc_type",
							fieldtype: "Link",
							options: "DocType",
							in_list_view: 1,
							in_standard_filter: 1,
						},
						{
							label: "Document ID",
							fieldname: "doc_id",
							fieldtype: "Dynamic Link",
							options: "doc_type",
							in_list_view: 1,
							in_standard_filter: 1,
						},
					],
				});
			});
	});

	function get_dialog_with_dynamic_link() {
		return cy.dialog({
			title: "Dynamic Link",
			fields: [
				{
					label: "Document Type",
					fieldname: "doc_type",
					fieldtype: "Link",
					options: "DocType",
					in_list_view: 1,
				},
				{
					label: "Document ID",
					fieldname: "doc_id",
					fieldtype: "Dynamic Link",
					options: "doc_type",
					in_list_view: 1,
				},
			],
		});
	}

	function get_dialog_with_dynamic_link_option() {
		return cy.dialog({
			title: "Dynamic Link",
			fields: [
				{
					label: "Document Type",
					fieldname: "doc_type",
					fieldtype: "Link",
					options: "DocType",
					in_list_view: 1,
				},
				{
					label: "Document ID",
					fieldname: "doc_id",
					fieldtype: "Dynamic Link",
					get_options: () => {
						return "User";
					},
					in_list_view: 1,
				},
			],
		});
	}

	it("Creating a dynamic link by passing option as function and verifying it in a dialog", () => {
		get_dialog_with_dynamic_link_option().as("dialog");
		cy.get_field("doc_type").clear();
		cy.fill_field("doc_type", "User", "Link");
		cy.get_field("doc_id").click();

		//Checking if the listbox have length greater than 0
		cy.get('[data-fieldname="doc_id"]')
			.find(".awesomplete")
			.find("div")
			.its("length")
			.should("be.gte", 0);
		cy.get(".btn-modal-close").click({ force: true });
	});

	it("Creating a dynamic link and verifying it in a dialog", () => {
		get_dialog_with_dynamic_link().as("dialog");
		cy.get_field("doc_type").clear();
		cy.fill_field("doc_type", "User", "Link");
		cy.get_field("doc_id").click();

		//Checking if the listbox have length greater than 0
		cy.get('[data-fieldname="doc_id"]')
			.find(".awesomplete")
			.find("div")
			.its("length")
			.should("be.gte", 0);
		cy.get(".btn-modal-close").click({ force: true, multiple: true });
	});

	it("Creating a dynamic link and verifying it", () => {
		cy.visit("/app/test-dynamic-link");

		//Clicking on the Document ID field
		cy.get_field("doc_type").clear();

		//Entering User in the Doctype field
		cy.fill_field("doc_type", "User", "Link", { delay: 500 });
		cy.get_field("doc_id").click();

		//Checking if the listbox have length greater than 0
		cy.get('[data-fieldname="doc_id"]')
			.find(".awesomplete")
			.find("div")
			.its("length")
			.should("be.gte", 0);

		//Opening a new form for dynamic link doctype
		cy.new_form("Test Dynamic Link");
		cy.get_field("doc_type").clear();

		//Entering User in the Doctype field
		cy.fill_field("doc_type", "User", "Link", { delay: 500 });
		cy.get_field("doc_id").click();

		//Checking if the listbox have length greater than 0
		cy.get('[data-fieldname="doc_id"]')
			.find(".awesomplete")
			.find("div")
			.its("length")
			.should("be.gte", 0);
		cy.get_field("doc_type").clear();

		//Entering System Settings in the Doctype field
		cy.intercept("/api/method/frappe.desk.search.search_link").as("search_query");
		cy.fill_field("doc_type", "System Settings", "Link", { delay: 500 });
		cy.wait("@search_query");
		cy.get(`[data-fieldname="doc_type"] ul:visible div:first-child`).click({
			scrollBehavior: false,
		});

		cy.get_field("doc_id").click();

		//Checking if the system throws error
		cy.get(".modal-title").should("have.text", "Error");
		cy.get(".msgprint").should(
			"have.text",
			"System Settings is not a valid DocType for Dynamic Link"
		);
	});
});
