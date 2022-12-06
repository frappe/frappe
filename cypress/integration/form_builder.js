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
});
