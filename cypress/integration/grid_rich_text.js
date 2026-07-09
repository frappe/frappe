context("Grid Rich Text Column", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.xcall("frappe.tests.ui_test_helpers.create_child_doctype", {
					name: "Child Test Rich Text",
					fields: [
						{
							label: "Title",
							fieldname: "title",
							fieldtype: "Data",
							in_list_view: 1,
						},
						{
							label: "Content",
							fieldname: "content",
							fieldtype: "Text Editor",
							in_list_view: 1,
						},
					],
				});
			})
			.then((frappe) => {
				return frappe.xcall("frappe.tests.ui_test_helpers.create_doctype", {
					name: "Test Rich Text Grid",
					fields: [
						{
							label: "Items",
							fieldname: "items",
							fieldtype: "Table",
							options: "Child Test Rich Text",
						},
					],
				});
			});
	});

	it("shows stripped text instead of rendered HTML in static grid cells", () => {
		cy.new_form("Test Rich Text Grid");
		cy.window()
			.its("cur_frm")
			.then((frm) => {
				frm.add_child("items", {
					title: "Row 1",
					content: "<h1>Heading</h1><p><b>bold</b> and <i>italic</i></p>",
				});
				frm.refresh_field("items");
			});

		cy.get('.frappe-control[data-fieldname="items"]').as("table");
		cy.get("@table")
			.find('.grid-body .grid-row [data-fieldname="content"] .static-area')
			.as("cell");
		cy.get("@cell").should("contain.text", "Heading");
		cy.get("@cell").should("contain.text", "bold and italic");
		cy.get("@cell").find("h1, b, i, .ql-editor").should("not.exist");
	});
});
