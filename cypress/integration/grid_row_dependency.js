import doctype_with_child_table from "../fixtures/doctype_with_child_table";
import child_table_doctype from "../fixtures/child_table_doctype";
import child_table_doctype_1 from "../fixtures/child_table_doctype_1";
const doctype_with_child_table_name = doctype_with_child_table.name;

context("Grid Row Dependency", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.insert_doc("DocType", child_table_doctype, true);
		cy.insert_doc("DocType", child_table_doctype_1, true);
		cy.insert_doc("DocType", doctype_with_child_table, true);
	});

	after(() => {
		cy.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.model.user_settings.save(
					doctype_with_child_table_name,
					"GridView",
					null
				);
			});
	});

	it("keeps a dependent column on rows whose dependency is met", () => {
		cy.visit("/desk/website");

		cy.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.model.user_settings.save(doctype_with_child_table_name, "GridView", {
					"Child Table Doctype 1": [
						{ fieldname: "data", columns: 3 },
						{ fieldname: "dependent_data", columns: 3 },
					],
				});
			});

		cy.new_form(doctype_with_child_table_name);

		cy.window()
			.its("cur_frm")
			.then((frm) => {
				frm.add_child("child_table_1", { data: "has data" });
				frm.add_child("child_table_1", {});
				frm.refresh();
			});

		cy.get('.frappe-control[data-fieldname="child_table_1"]').as("table");

		cy.get("@table").find(".grid-body .rows .grid-row").eq(1).find(".data-row").click();
		cy.get("@table")
			.find(".grid-body .rows .grid-row")
			.eq(1)
			.find('[data-fieldname="dependent_data"] input')
			.should("not.exist");

		cy.get("@table").find(".grid-body .rows .grid-row").eq(0).find(".data-row").click();
		cy.get("@table")
			.find(".grid-body .rows .grid-row")
			.eq(0)
			.find('[data-fieldname="dependent_data"] input')
			.should("be.visible");
	});
});
