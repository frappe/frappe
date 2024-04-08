import form_builder_doctype from "../fixtures/form_builder_doctype";
const doctype_name = form_builder_doctype.name;
context("Form Builder", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
		return cy.insert_doc("DocType", form_builder_doctype, true);
	});

	it("Open Form Builder for Web Form Doctype/Customize Form", () => {
		// doctype
		cy.visit("/app/doctype/Web Form");
		cy.findByRole("tab", { name: "Form" }).click();
		cy.get(".form-builder-container").should("exist");

		// customize form
		cy.visit("/app/customize-form?doc_type=Web%20Form");
		cy.findByRole("tab", { name: "Form" }).click();
		cy.get(".form-builder-container").should("exist");
	});

	it("Save without change, check form dirty", () => {
		cy.visit(`/app/doctype/${doctype_name}`);
		cy.findByRole("tab", { name: "Form" }).click();

		// Save without change
		cy.click_doc_primary_button("Save");
		cy.get(".desk-alert.orange .alert-message").should("have.text", "No changes in document");

		// Check form dirty
		cy.get(".tab-content.active .section-columns-container:first .column:first .field:first")
			.find("div[title='Double click to edit label']")
			.dblclick()
			.type("Dirty");
		cy.get(".title-area .indicator-pill.orange").should("have.text", "Not Saved");
	});

	it("Check if Filters are applied to the link field", () => {
		// Visit the Form Builder
		cy.visit(`/app/doctype/${doctype_name}`);
		cy.findByRole("tab", { name: "Form" }).click();

		cy.get("[data-fieldname='gender']").click();

		// click on filter action button
		cy.get('[data-fieldname="gender"] .field-actions button:first').click();

		// add filter
		cy.get(".modal-body .clear-filters").click();
		cy.get(".modal-body .filter-action-buttons .add-filter").click();
		cy.wait(100);
		cy.get(".modal-body .filter-box .list_filter .filter-field .link-field input").type(
			"Male"
		);
		cy.get(".btn-modal-primary").click();

		// Save the document
		cy.click_doc_primary_button("Save");

		// Open a new Form
		cy.new_form(doctype_name);
		// Click on the "salutation" field
		cy.get_field("gender").clear().click();

		cy.intercept("POST", "/api/method/frappe.desk.search.search_link").as("search_link");
		cy.wait("@search_link").then((data) => {
			expect(data.response.body.message.length).to.eq(1);
			expect(data.response.body.message[0].value).to.eq("Male");
		});
	});

	it("Add empty section and save", () => {
		cy.visit(`/app/doctype/${doctype_name}`);
		cy.findByRole("tab", { name: "Form" }).click();

		let first_section = ".tab-content.active .form-section-container:first";

		// add new section
		cy.get(first_section).click(15, 10);
		cy.get(first_section).find(".dropdown-btn:first").click();
		cy.get(".dropdown-options:visible .dropdown-item:first").click();

		// save
		cy.click_doc_primary_button("Save");
		cy.get(".tab-content.active .form-section-container").should("have.length", 1);
	});

	it("Add Table field and check if columns are rendered", () => {
		cy.intercept("POST", "/api/method/frappe.desk.search.search_link").as("search_link");

		cy.visit(`/app/doctype/${doctype_name}`);
		cy.findByRole("tab", { name: "Form" }).click();

		let first_column = ".tab-content.active .section-columns-container:first .column:first";

		let last_field = first_column + " .field:last";

		let add_new_field_btn = first_column + " .add-new-field-btn button";

		// add new field
		cy.get(add_new_field_btn).click();

		// type table and press enter
		cy.get(".combo-box-options:visible .search-box > input").type("table{enter}");

		// save
		cy.click_doc_primary_button("Save");

		// Validate if options is not set
		cy.get_open_dialog().find(".msgprint").should("contain", "Options is required");
		cy.hide_dialog();

		cy.get(last_field).click({ force: true });

		cy.get(".sidebar-container .frappe-control[data-fieldname='options'] input")
			.click()
			.as("input");
		cy.get("@input").clear({ force: true }).type("Web Form Field", { delay: 200 });
		cy.wait("@search_link");

		cy.get(last_field).click({ force: true });

		cy.get(last_field).find(".table-controls .table-column").contains("Field").should("exist");
		cy.get(last_field)
			.find(".table-controls .table-column")
			.contains("Fieldtype")
			.should("exist");

		// validate In List View
		cy.get(".sidebar-container .field label .label-area").contains("In List View").click();

		// save
		cy.click_doc_primary_button("Save");

		cy.get_open_dialog().find(".msgprint").should("contain", "In List View");
		cy.hide_dialog();

		cy.get(last_field).click({ force: true });
		cy.get(".sidebar-container .field label .label-area").contains("In List View").click();

		// validate In Global Search
		cy.get(".sidebar-container .field label .label-area").contains("In Global Search").click();
		// save
		cy.click_doc_primary_button("Save");

		cy.get_open_dialog().find(".msgprint").should("contain", "In Global Search");
	});
	// not important and was flaky on CI
	it.skip("Drag Field/Column/Section & Tab", () => {
		cy.visit(`/app/doctype/${doctype_name}`);
		cy.findByRole("tab", { name: "Form" }).click();

		let first_column = ".tab-content.active .section-columns-container:first .column:first";
		let first_field = first_column + " .field:first";
		let label = "div[title='Double click to edit label'] span:first";

		cy.get(".tab-header .tabs .tab:first").click();

		// drag first tab to second position
		cy.get(".tab-header .tabs .tab:first").drag(".tab-header .tabs .tab:nth-child(2)", {
			target: { x: 10, y: 10 },
			force: true,
		});
		cy.get(".tab-header .tabs .tab:first").find(label).should("have.text", "Tab 2");

		cy.get(".tab-header .tabs .tab:first").click();
		cy.get(".sidebar-container .tab:first").click();

		// drag check field to first column
		cy.get(".fields-container .field[title='Check']").drag(first_field, {
			target: { x: 100, y: 10 },
		});
		cy.get(first_column).find(".field").should("have.length", 3);

		cy.get(first_field)
			.find("div[title='Double click to edit label']")
			.dblclick()
			.type("Test Check");
		cy.get(first_field).find(label).should("have.text", "Test Check");

		// drag the first field to second position
		cy.get(first_field).drag(first_column + " .field:nth-child(2)", {
			target: { x: 100, y: 10 },
		});
		cy.get(first_field).find(label).should("have.text", "Data");

		// drag first column to second position
		cy.get(first_column).click().wait(200);
		cy.get(first_column)
			.find(".column-actions")
			.drag(".section-columns-container:first .column:last", {
				target: { x: 100, y: 10 },
				force: true,
			});
		cy.get(first_field).find(label).should("have.text", "Data 1");

		let first_section = ".tab-content.active .form-section-container:first";

		// drag first section to second position
		cy.get(first_section).click().wait(200);
		cy.get(first_section)
			.find(".section-header")
			.drag(".form-section-container:nth-child(2)", {
				target: { x: 100, y: 10 },
				force: true,
			});
		cy.get(first_field).find(label).should("have.text", "Data 2");
	});

	it("Add New Tab/Section/Column to Form", () => {
		cy.visit(`/app/doctype/${doctype_name}`);
		cy.findByRole("tab", { name: "Form" }).click();

		let first_section = ".tab-content.active .form-section-container:first";

		// add new tab
		cy.get(".tab-header").realHover().find(".tab-actions .new-tab-btn").click();
		cy.get(".tab-header .tabs .tab").should("have.length", 3);

		// add new section
		cy.get(first_section).click(15, 10);
		cy.get(first_section).find(".dropdown-btn:first").click();
		cy.get(".dropdown-options:visible .dropdown-item:first").click();
		cy.get(".tab-content.active .form-section-container").should("have.length", 2);

		// add new column
		cy.get(first_section).click(15, 10);
		cy.get(first_section).find(".dropdown-btn:first").click();
		cy.get(".dropdown-options:visible .dropdown-item:last").click();
		cy.get(first_section).find(".column").should("have.length", 2);
	});

	it("Remove Tab/Section/Column", () => {
		let first_section = ".tab-content.active .form-section-container:first";

		// remove column
		cy.get(first_section).click(15, 10);
		cy.get(first_section).find(".dropdown-btn:first").click();
		cy.get(".dropdown-options:visible .dropdown-item:last").click();
		cy.get(first_section).find(".column").should("have.length", 1);

		// remove section
		cy.get(first_section).click(15, 10);
		cy.get(first_section).find(".dropdown-btn:first").click();
		cy.get(".dropdown-options:visible .dropdown-item").eq(1).click();
		cy.get(".tab-content.active .form-section-container").should("have.length", 1);

		// remove tab
		cy.get(".tab-header .tab:last").realHover().find(".remove-tab-btn").click();
		cy.get(".tab-header .tabs .tab").should("have.length", 2);
	});

	it("Update Title field Label to New Title through Customize Form", () => {
		cy.visit(`/app/doctype/${doctype_name}`);
		cy.findByRole("tab", { name: "Form" }).click();

		let first_field =
			".tab-content.active .section-columns-container:first .column:first .field:first";

		cy.get(first_field)
			.find("div[title='Double click to edit label']")
			.dblclick()
			.type("{selectall}New Title");

		cy.findByRole("button", { name: "Save" }).click({ force: true });

		cy.visit("/app/form-builder-doctype/new");
		cy.get("[data-fieldname='data3'] .clearfix label").should("have.text", "New Title");
	});

	it("Validate Duplicate Name & reqd + hidden without default logic", () => {
		cy.visit(`/app/doctype/${doctype_name}`);
		cy.findByRole("tab", { name: "Form" }).click();

		let first_column = ".tab-content.active .section-columns-container:first .column:first";

		let last_field = first_column + " .field:last";

		let add_new_field_btn = first_column + " .add-new-field-btn button";

		// add new field
		cy.get(add_new_field_btn).click();

		// type data and press enter
		cy.get(".combo-box-options:visible .search-box > input").type("data{enter}");

		cy.get(last_field).click();

		// validate duplicate name
		cy.get(".sidebar-container .frappe-control[data-fieldname='fieldname'] input")
			.click()
			.as("input");
		cy.get(".sidebar-container .frappe-control[data-fieldname='fieldname'] input")
			.clear({ force: true })
			.type("data3");

		cy.click_doc_primary_button("Save");
		cy.get_open_dialog().find(".msgprint").should("contain", "appears multiple times");
		cy.hide_dialog();
		cy.get(last_field).click();
		cy.get(".sidebar-container .frappe-control[data-fieldname='fieldname'] input").clear({
			force: true,
		});

		// validate reqd + hidden without default
		cy.get(".sidebar-container .field label .label-area").contains("Mandatory").click();
		cy.get(".sidebar-container .field label .label-area").contains("Hidden").click();

		// save
		cy.click_doc_primary_button("Save");

		cy.get_open_dialog()
			.find(".msgprint")
			.should("contain", "cannot be hidden and mandatory without any default value");
	});

	it.skip("Undo/Redo", () => {
		cy.visit(`/app/doctype/${doctype_name}`);
		cy.findByRole("tab", { name: "Form" }).click();

		// click on second tab
		cy.get(".tab-header .tabs .tab:last").click();

		let first_column = ".tab-content.active .section-columns-container:first .column:first";
		let first_field = first_column + " .field:first";
		let label = "div[title='Double click to edit label'] span:first";

		// drag the first field to second position
		cy.get(first_field).drag(first_column + " .field:nth-child(2)", {
			target: { x: 100, y: 10 },
		});
		cy.get(first_field).find(label).should("have.text", "Check");

		// undo
		cy.get("body").type("{ctrl}z");
		cy.get(first_field).find(label).should("have.text", "Data");

		// redo
		cy.get("body").type("{ctrl}{shift}z");
		cy.get(first_field).find(label).should("have.text", "Check");
	});
});
