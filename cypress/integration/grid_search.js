import doctype_with_child_table from "../fixtures/doctype_with_child_table";
import child_table_doctype from "../fixtures/child_table_doctype";
import child_table_doctype_1 from "../fixtures/child_table_doctype_1";
const doctype_with_child_table_name = doctype_with_child_table.name;

context("Grid Search", () => {
	before(() => {
		cy.visit("/login");
		cy.login();
		cy.visit("/app/website");
		cy.insert_doc("DocType", child_table_doctype, true);
		cy.insert_doc("DocType", child_table_doctype_1, true);
		cy.insert_doc("DocType", doctype_with_child_table, true);
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.xcall(
					"frappe.tests.ui_test_helpers.insert_doctype_with_child_table_record",
					{
						name: doctype_with_child_table_name,
					}
				);
			});
	});

	it("Test search row visibility", () => {
		cy.window()
			.its("frappe")
			.then((frappe) => {
				frappe.model.user_settings.save("Doctype With Child Table", "GridView", {
					"Child Table Doctype 1": [
						{ fieldname: "data", columns: 2 },
						{ fieldname: "barcode", columns: 1 },
						{ fieldname: "check", columns: 1 },
						{ fieldname: "rating", columns: 2 },
						{ fieldname: "duration", columns: 2 },
						{ fieldname: "date", columns: 2 },
					],
				});
			});

		cy.visit(`/app/doctype-with-child-table/Test Grid Search`);

		cy.get('.frappe-control[data-fieldname="child_table_1"]').as("table");
		cy.get("@table").find(".grid-row-check:last").click();
		cy.get("@table").find(".grid-footer").contains("Delete").click();
		cy.get(".grid-heading-row .grid-row .search").should("not.exist");
	});

	it("test search field for different fieldtypes", () => {
		cy.visit(`/app/doctype-with-child-table/Test Grid Search`);

		cy.get('.frappe-control[data-fieldname="child_table_1"]').as("table");

		// Index Column
		cy.get("@table").find(".grid-heading-row .row-index.search input").type("3");
		cy.get("@table").find(".grid-body .rows .grid-row").should("have.length", 2);
		cy.get("@table").find(".grid-heading-row .row-index.search input").clear();

		// Data Column
		cy.get("@table")
			.find('.grid-heading-row .search input[data-fieldtype="Data"]')
			.type("Data");
		cy.get("@table").find(".grid-body .rows .grid-row").should("have.length", 1);
		cy.get("@table").find('.grid-heading-row .search input[data-fieldtype="Data"]').clear();

		// Barcode Column
		cy.get("@table")
			.find('.grid-heading-row .search input[data-fieldtype="Barcode"]')
			.type("092");
		cy.get("@table").find(".grid-body .rows .grid-row").should("have.length", 4);
		cy.get("@table").find('.grid-heading-row .search input[data-fieldtype="Barcode"]').clear();

		// Check Column
		cy.get("@table").find('.grid-heading-row .search input[data-fieldtype="Check"]').type("1");
		cy.get("@table").find(".grid-body .rows .grid-row").should("have.length", 9);
		cy.get("@table").find('.grid-heading-row .search input[data-fieldtype="Check"]').clear();

		cy.get("@table").find('.grid-heading-row .search input[data-fieldtype="Check"]').type("0");
		cy.get("@table").find(".grid-body .rows .grid-row").should("have.length", 11);
		cy.get("@table").find('.grid-heading-row .search input[data-fieldtype="Check"]').clear();

		// Rating Column
		cy.get("@table")
			.find('.grid-heading-row .search input[data-fieldtype="Rating"]')
			.type("3");
		cy.get("@table").find(".grid-body .rows .grid-row").should("have.length", 3);
		cy.get("@table").find('.grid-heading-row .search input[data-fieldtype="Rating"]').clear();

		// Duration Column
		cy.get("@table")
			.find('.grid-heading-row .search input[data-fieldtype="Duration"]')
			.type("3d");
		cy.get("@table").find(".grid-body .rows .grid-row").should("have.length", 3);
		cy.get("@table")
			.find('.grid-heading-row .search input[data-fieldtype="Duration"]')
			.clear();

		// Date Column
		cy.get("@table")
			.find('.grid-heading-row .search input[data-fieldtype="Date"]')
			.type("2022");
		cy.get("@table").find(".grid-body .rows .grid-row").should("have.length", 4);
		cy.get("@table").find('.grid-heading-row .search input[data-fieldtype="Date"]').clear();
	});

	it("test with multiple filter", () => {
		cy.get('.frappe-control[data-fieldname="child_table_1"]').as("table");

		// Data Column
		cy.get("@table").find('.grid-heading-row .search input[data-fieldtype="Data"]').type("a");
		cy.get("@table").find(".grid-body .rows .grid-row").should("have.length", 10);

		// Barcode Column
		cy.get("@table")
			.find('.grid-heading-row .search input[data-fieldtype="Barcode"]')
			.type("0");
		cy.get("@table").find(".grid-body .rows .grid-row").should("have.length", 8);

		// Duration Column
		cy.get("@table")
			.find('.grid-heading-row .search input[data-fieldtype="Duration"]')
			.type("d");
		cy.get("@table").find(".grid-body .rows .grid-row").should("have.length", 5);

		// Date Column
		cy.get("@table")
			.find('.grid-heading-row .search input[data-fieldtype="Date"]')
			.type("02-");
		cy.get("@table").find(".grid-body .rows .grid-row").should("have.length", 2);
	});
});
