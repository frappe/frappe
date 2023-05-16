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
		cy.visit("/app/form-builder/Web Form");
		cy.get(".form-builder-container").should("exist");

		// customize form
		cy.visit("/app/form-builder/Web Form/customize");
		cy.get(".form-builder-container").should("exist");
	});

	it("Change Doctype using page title dialog", () => {
		cy.intercept("POST", "/api/method/frappe.desk.search.search_link").as("search_link");

		cy.visit(`/app/form-builder/Web Form`);
		cy.get(".form-builder-container").should("exist");

		cy.get(".page-title").click();

		cy.get(".frappe-control[data-fieldname='doctype'] input").click().as("input");
		cy.get("@input").type("{rightArrow} Field", { delay: 200 });
		cy.wait("@search_link");
		cy.get("@input").type("{enter}").blur();

		cy.click_modal_primary_button("Change");

		cy.get(".page-title .title-text").should("have.text", "Web Form Field");
	});

	it("Save without change, check form dirty and reset changes", () => {
		cy.visit(`/app/form-builder/${doctype_name}`);

		// Save without change
		cy.click_doc_primary_button("Save");
		cy.get(".desk-alert.orange .alert-message").should("have.text", "No changes to save");

		// Check form dirty
		cy.get(".tab-content.active .section-columns-container:first .column:first .field:first")
			.find("div[title='Double click to edit label']")
			.dblclick()
			.type("Dirty");
		cy.get(".title-area .indicator-pill.orange").should("have.text", "Not Saved");

		// Reset changes
		cy.get(".page-actions .custom-actions .btn").contains("Reset Changes").click();
		cy.get(".title-area .indicator-pill.orange").should("not.exist");
	});

	it("Add empty section and save", () => {
		cy.visit(`/app/form-builder/${doctype_name}`);

		let first_section = ".tab-content.active .form-section-container:first";

		// add new section
		cy.get(first_section).click(15, 10);
		cy.get(first_section).find(".section-actions button:first").click();

		// save
		cy.click_doc_primary_button("Save");
		cy.get(".tab-content.active .form-section-container").should("have.length", 1);
	});

	it("Add Table field and check if columns are rendered", () => {
		cy.intercept("POST", "/api/method/frappe.desk.search.search_link").as("search_link");

		cy.visit(`/app/form-builder/${doctype_name}`);

		let first_field =
			".tab-content.active .section-columns-container:first .column:first .field:first";

		cy.get(".fields-container .field[title='Table']").drag(first_field, {
			target: { x: 100, y: 10 },
		});

		// save
		cy.click_doc_primary_button("Save");

		// Validate if options is not set
		cy.get_open_dialog().find(".msgprint").should("contain", "Options is required");
		cy.hide_dialog();

		cy.get(first_field).click({ force: true });

		cy.get(".sidebar-container .frappe-control[data-fieldname='options'] input")
			.click()
			.as("input");
		cy.get("@input").clear({ force: true }).type("Web Form Field", { delay: 200 });
		cy.wait("@search_link");
		cy.get("@input").type("{enter}").blur();

		cy.get(first_field)
			.find(".table-controls .table-column")
			.contains("Field")
			.should("exist");
		cy.get(first_field)
			.find(".table-controls .table-column")
			.contains("Fieldtype")
			.should("exist");

		// validate In List View
		cy.get(".sidebar-container .field label .label-area").contains("In List View").click();

		// save
		cy.click_doc_primary_button("Save");

		cy.get_open_dialog().find(".msgprint").should("contain", "In List View");
		cy.hide_dialog();

		cy.get(first_field).click({ force: true });
		cy.get(".sidebar-container .field label .label-area").contains("In List View").click();

		// validate In Global Search
		cy.get(".sidebar-container .field label .label-area").contains("In Global Search").click();
		// save
		cy.click_doc_primary_button("Save");

		cy.get_open_dialog().find(".msgprint").should("contain", "In Global Search");
	});

	it("Drag Field/Column/Section & Tab", () => {
		cy.visit(`/app/form-builder/${doctype_name}`);

		let first_column = ".tab-content.active .section-columns-container:first .column:first";
		let first_field = first_column + " .field:first";
		let label = "div[title='Double click to edit label'] span:first";

		// drag first tab to second position
		cy.get(".tabs .tab:first").drag(".tabs .tab:nth-child(2)", {
			target: { x: 10, y: 10 },
			force: true,
		});
		cy.get(".tabs .tab:first").find(label).should("have.text", "Tab 2");

		cy.get(".tabs .tab:first").click();
		cy.get(".sidebar-container .tab:first").click();

		// drag check field to first column
		cy.get(".fields-container .field[title='Check']").drag(first_field, {
			target: { x: 100, y: 10 },
		});
		cy.get(first_column).find(".field").should("have.length", 3);

		cy.get(first_field)
			.find("div[title='Double click to edit label']")
			.dblclick()
			.type("Test Check{enter}");
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
		cy.visit(`/app/form-builder/${doctype_name}`);

		let first_section = ".tab-content.active .form-section-container:first";

		// add new tab
		cy.get(".tab-header").realHover().find(".tab-actions .new-tab-btn").click();
		cy.get(".tabs .tab").should("have.length", 3);

		// add new section
		cy.get(first_section).click(15, 10);
		cy.get(first_section).find(".section-actions button:first").click();
		cy.get(".tab-content.active .form-section-container").should("have.length", 2);

		// add new column
		cy.get(first_section).find(".column:first").click(15, 10);
		cy.get(first_section).find(".column:first .column-actions button:first").click();
		cy.get(first_section).find(".column").should("have.length", 3);
	});

	it("Remove Tab/Section/Column", () => {
		let first_section = ".tab-content.active .form-section-container:first";

		// remove column
		cy.get(first_section).find(".column:first").click(15, 10);
		cy.get(first_section).find(".column:first .column-actions button:last").click();
		cy.get(first_section).find(".column").should("have.length", 2);

		// remove section
		cy.get(first_section).click(15, 10);
		cy.get(first_section).find(".section-actions button:last").click();
		cy.get(".tab-content.active .form-section-container").should("have.length", 1);

		// remove tab
		cy.get(".tab-header").realHover().find(".tab-actions .remove-tab-btn").click();
		cy.get(".tabs .tab").should("have.length", 2);
	});

	it("Update Title field Label to New Title through Customize Form", () => {
		cy.visit(`/app/form-builder/${doctype_name}`);

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
		cy.visit(`/app/form-builder/${doctype_name}`);

		let first_field =
			".tab-content.active .section-columns-container:first .column:first .field:first";

		cy.get(".fields-container .field[title='Data']").drag(first_field, {
			target: { x: 100, y: 10 },
		});

		cy.get(first_field).click();

		// validate duplicate name
		cy.get(".sidebar-container .frappe-control[data-fieldname='fieldname'] input")
			.click()
			.as("input");
		cy.get("@input").clear({ force: true }).type("data3");

		cy.click_doc_primary_button("Save");
		cy.get_open_dialog().find(".msgprint").should("contain", "appears multiple times");
		cy.hide_dialog();
		cy.get(first_field).click();
		cy.get("@input").clear({ force: true });

		// validate reqd + hidden without default
		cy.get(".sidebar-container .field label .label-area").contains("Mandatory").click();
		cy.get(".sidebar-container .field label .label-area").contains("Hidden").click();

		// save
		cy.click_doc_primary_button("Save");

		cy.get_open_dialog()
			.find(".msgprint")
			.should("contain", "cannot be hidden and mandatory without any default value");
	});

	it("Undo/Redo", () => {
		cy.visit(`/app/form-builder/${doctype_name}`);

		// click on second tab
		cy.get(".tabs .tab:last").click();

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
