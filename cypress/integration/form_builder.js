context("Form Builder", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
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
		cy.visit("/app/form-builder/Web Form");

		cy.get(".section-columns-container:first .column:first").as("first-column");
		cy.get(".section-columns-container:first .column:first .field:first").as("first-field");

		cy.get("@first-field")
			.find("div[title='Double click to edit label'] span:first")
			.as("first-field-title");

		// drag check field to first column
		cy.get(".fields-container .field[title='Check']").drag(
			".section-columns-container:first .column:first .field:first",
			{
				target: { x: 100, y: 10 },
			}
		);
		cy.get("@first-column").find(".field").should("have.length", 4);

		cy.get("@first-field")
			.find("div[title='Double click to edit label']")
			.dblclick()
			.type("Test Check{enter}");
		cy.get("@first-field-title").should("have.text", "Test Check");

		// drag the first field to second position
		cy.get("@first-field").drag(
			".section-columns-container:first .column:first .field:nth-child(2)",
			{
				target: { x: 100, y: 10 },
			}
		);
		cy.get("@first-field-title").should("have.text", "Title");

		// drag first column to second position
		cy.get("@first-column").click().wait(200);
		cy.get("@first-column")
			.find(".column-actions")
			.drag(".section-columns-container:first .column:last", {
				target: { x: 100, y: 10 },
				force: true,
			});
		cy.get("@first-field-title").should("have.text", "Select DocType");

		cy.get(".form-section-container:first").as("first-section");

		// drag first section to second position
		cy.get("@first-section").click().wait(200);
		cy.get("@first-section")
			.find(".section-header")
			.drag(".form-section-container:nth-child(2)", {
				target: { x: 100, y: 10 },
				force: true,
			});
		cy.get(".section-columns-container:first .column:first .field:first").as("first-field");
		cy.get("@first-field-title").should("have.text", "Introduction");

		cy.get(".tabs .tab:first").as("first-tab");
		cy.get("@first-tab")
			.find("div[title='Double click to edit label'] span:first")
			.as("first-tab-title");

		// drag first tab to second position
		cy.get("@first-tab").drag(".tabs .tab:nth-child(2)", {
			target: { x: 10, y: 10 },
			force: true,
		});
		cy.get("@first-tab-title").should("have.text", "Settings");
	});

	it("Add New Tab/Section/Column to Form", () => {
		cy.visit("/app/form-builder/Web Form");

		// add new tab
		cy.get(".tab-header").realHover().find(".tab-actions .new-tab-btn").click();
		cy.get(".tabs .tab").should("have.length", 4);

		cy.get(".tab-content.active .form-section-container:first").as("first-section");

		// add new section
		cy.get("@first-section").click(15, 10);
		cy.get("@first-section").find(".section-actions button:first").click();
		cy.get(".tab-content.active .form-section-container").should("have.length", 2);

		// add new column
		cy.get("@first-section").find(".column:first").click(15, 10);
		cy.get("@first-section").find(".column:first .column-actions button:first").click();
		cy.get("@first-section").find(".column").should("have.length", 3);
	});

	it("Remove Tab/Section/Column", () => {
		cy.get(".tab-content.active .form-section-container:first").as("first-section");

		// remove column
		cy.get("@first-section").find(".column:first").click(15, 10);
		cy.get("@first-section").find(".column:first .column-actions button:last").click();
		cy.get("@first-section").find(".column").should("have.length", 2);

		// remove section
		cy.get("@first-section").click(15, 10);
		cy.get("@first-section").find(".section-actions button:last").click();
		cy.get(".tab-content.active .form-section-container").should("have.length", 1);

		// remove tab
		cy.get(".tab-header").realHover().find(".tab-actions .remove-tab-btn").click();
		cy.get(".tabs .tab").should("have.length", 3);
	});

	it("Update Title field Label to New Title through Customize Form", () => {
		cy.visit("/app/form-builder/Web Form/customize");

		cy.get(".section-columns-container:first .column:first .field:first")
			.find("div[title='Double click to edit label']")
			.dblclick()
			.type("{selectall}New Title");

		cy.findByRole("button", { name: "Save" }).click({ force: true });

		cy.visit("/app/web-form/new");
		cy.get("[data-fieldname='title'] .clearfix label").should("have.text", "New Title");
	});
});
