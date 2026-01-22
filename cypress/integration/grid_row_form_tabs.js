import child_table_with_tabs from "../fixtures/child_table_with_tabs";
import doctype_with_child_table_tabs from "../fixtures/doctype_with_child_table_tabs";

const parent_doctype_name = doctype_with_child_table_tabs.name;
const child_doctype_name = child_table_with_tabs.name;

context("Grid Row Form Tabs", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		// Create child table doctype first, then parent
		return cy.insert_doc("DocType", child_table_with_tabs, true).then(() => {
			return cy.insert_doc("DocType", doctype_with_child_table_tabs, true);
		});
	});

	beforeEach(() => {
		cy.login();
		cy.visit("/desk/website");
	});

	it("should display tabs in grid row form", () => {
		cy.new_form(parent_doctype_name);
		cy.fill_field("title", "Test Document");

		// Add a row to the child table
		cy.get('.frappe-control[data-fieldname="items"]').as("table");
		cy.get("@table").findByRole("button", { name: "Add row" }).click();

		// Open the grid row form
		cy.get("@table").find('[data-idx="1"]').as("row1");
		cy.get("@row1").find(".btn-open-row").click();

		// Verify grid row form is open
		cy.get(".grid-row-open").as("table-form");

		// Verify tabs are visible in the grid row form
		cy.get("@table-form").find(".form-tabs-list").should("be.visible");
		cy.get("@table-form").find(".form-tabs .nav-item").should("have.length", 2);

		// Verify first tab (General) is active by default
		cy.get("@table-form").find(".form-tabs .nav-link").first().should("have.class", "active");
	});

	it("should switch tabs in grid row form", () => {
		cy.new_form(parent_doctype_name);
		cy.fill_field("title", "Test Tab Switch");

		// Add a row to the child table
		cy.get('.frappe-control[data-fieldname="items"]').as("table");
		cy.get("@table").findByRole("button", { name: "Add row" }).click();

		// Open the grid row form
		cy.get("@table").find('[data-idx="1"]').as("row1");
		cy.get("@row1").find(".btn-open-row").click();
		cy.get(".grid-row-open").as("table-form");

		// Verify initial tab content - fields from General tab should be visible
		cy.get("@table-form")
			.find('.frappe-control[data-fieldname="item_name"]')
			.should("be.visible");
		cy.get("@table-form")
			.find('.frappe-control[data-fieldname="quantity"]')
			.should("be.visible");

		// Click on the "Details" tab and wait for it to become active
		cy.get("@table-form")
			.find('.form-tabs .nav-link[data-fieldname="tab_details"]')
			.click()
			.should("have.class", "active");

		// Verify first tab is no longer active
		cy.get("@table-form")
			.find(".form-tabs .nav-link")
			.first()
			.should("not.have.class", "active");

		// Fields from Details tab should be visible
		cy.get("@table-form")
			.find('.frappe-control[data-fieldname="description"]')
			.should("be.visible");
		cy.get("@table-form").find('.frappe-control[data-fieldname="notes"]').should("be.visible");
	});

	it("should preserve tab state when switching between rows", () => {
		cy.new_form(parent_doctype_name);
		cy.fill_field("title", "Test Tab Persistence");

		// Add two rows to the child table
		cy.get('.frappe-control[data-fieldname="items"]').as("table");
		cy.get("@table").findByRole("button", { name: "Add row" }).click();
		cy.get("@table").findByRole("button", { name: "Add row" }).click();

		// Open first row and switch to Details tab
		cy.get("@table").find('[data-idx="1"]').as("row1");
		cy.get("@row1").find(".btn-open-row").click();
		cy.get(".grid-row-open").as("table-form");
		cy.get("@table-form")
			.find('.form-tabs .nav-link[data-fieldname="tab_details"]')
			.click()
			.should("have.class", "active");

		// Collapse first row
		cy.get("@table-form").find(".grid-collapse-row").click();

		// Open second row - should show first tab by default (not persist from row 1)
		cy.get("@table").find('[data-idx="2"]').as("row2");
		cy.get("@row2").find(".btn-open-row").click();
		cy.get(".grid-row-open").as("table-form2");

		// First tab should be active in new row
		cy.get("@table-form2").find(".form-tabs .nav-link").first().should("have.class", "active");
	});

	it("should allow data entry in fields across different tabs", () => {
		cy.new_form(parent_doctype_name);
		cy.fill_field("title", "Test Data Entry");

		// Add a row to the child table
		cy.get('.frappe-control[data-fieldname="items"]').as("table");
		cy.get("@table").findByRole("button", { name: "Add row" }).click();

		// Open the grid row form
		cy.get("@table").find('[data-idx="1"]').as("row1");
		cy.get("@row1").find(".btn-open-row").click();
		cy.get(".grid-row-open").as("table-form");

		// Fill fields in first tab
		cy.fill_table_field("items", "1", "item_name", "Test Item");
		cy.fill_table_field("items", "1", "quantity", "10");

		// Switch to Details tab and wait for it to become active
		cy.get("@table-form")
			.find('.form-tabs .nav-link[data-fieldname="tab_details"]')
			.click()
			.should("have.class", "active");

		// Wait for tab content to be visible, then fill fields in second tab
		cy.get("@table-form")
			.find('.frappe-control[data-fieldname="description"]')
			.should("be.visible");
		cy.fill_table_field("items", "1", "description", "This is a test description");
		cy.fill_table_field("items", "1", "notes", "Some notes here");

		// Switch back to first tab and wait for it to become active
		cy.get("@table-form")
			.find('.form-tabs .nav-link[data-fieldname="tab_general"]')
			.click()
			.should("have.class", "active");
		cy.get("@table-form")
			.find('.frappe-control[data-fieldname="item_name"] input')
			.should("have.value", "Test Item");
	});
});
