const PARENT = "Fmt Parent";
const CHILD = "Fmt Child";

function newDoc(name) {
	cy.new_form(PARENT);
	cy.fill_field("name1", name, "Data");
	cy.save();
	cy.location("pathname").should("not.contain", "/new-");
}

function addRow(fields) {
	cy.get('.frappe-control[data-fieldname="items"]').as("tbl");
	cy.get("@tbl").find(".grid-add-row").click();
	cy.get("@tbl").find('[data-idx="1"] .btn-open-row').click();
	Object.entries(fields).forEach(([fn, [val, ft]]) =>
		cy.fill_table_field("items", 1, fn, val, ft)
	);
	cy.get("@tbl").find('[data-idx="1"] .form-in-grid .grid-collapse-row').click();
	cy.save();
}

function cell(fieldname) {
	return cy
		.get('.frappe-control[data-fieldname="items"]')
		.find(`.grid-row[data-idx="1"] [data-fieldname="${fieldname}"] .static-area`);
}

context("Formatters - Child Table", () => {
	before(() => {
		cy.login();
		cy.visit("/desk");
		cy.window()
			.its("frappe")
			.then((f) =>
				f
					.xcall("frappe.tests.ui_test_helpers.create_child_doctype", {
						name: CHILD,
						fields: [
							{
								label: "Title",
								fieldname: "title",
								fieldtype: "Data",
								in_list_view: 1,
							},
							{
								label: "Subtitle",
								fieldname: "subtitle",
								fieldtype: "Data",
								in_list_view: 1,
							},
							{
								label: "Description",
								fieldname: "description",
								fieldtype: "Small Text",
								in_list_view: 1,
							},
							{
								label: "Notes",
								fieldname: "notes",
								fieldtype: "Small Text",
								in_list_view: 1,
							},
						],
					})
					.then(() =>
						f.xcall("frappe.tests.ui_test_helpers.create_doctype", {
							name: PARENT,
							fields: [
								{ label: "Name", fieldname: "name1", fieldtype: "Data", reqd: 1 },
								{
									label: "Items",
									fieldname: "items",
									fieldtype: "Table",
									options: CHILD,
								},
							],
						})
					)
			);
	});

	beforeEach(() => {
		cy.login();
		cy.visit("/desk");
	});

	// <b> is in acceptable_elements so it survives sanitize_html; Data formatter must escape it.
	it("escapes <b> in Data cell", () => {
		newDoc("Bold Tag");
		addRow({ title: ["<b>bold</b>", "Data"] });
		cell("title").should("have.text", "<b>bold</b>");
		cell("title").find("b").should("not.exist");
	});

	// <img> survives sanitize_html; Data formatter must not render an img element.
	it("escapes <img> in Data cell", () => {
		newDoc("Img Tag");
		addRow({ subtitle: ["<img src=x>", "Data"] });
		cell("subtitle").find("img").should("not.exist");
		cell("subtitle").should("contain.text", "<img");
	});

	// <b> survives sanitize_html for Small Text; Text formatter must escape it.
	it("escapes <b> in Small Text cell", () => {
		newDoc("SmallText Bold");
		addRow({ title: ["row1", "Data"], description: ["<b>hello</b>", "Small Text"] });
		cell("description").should("have.text", "<b>hello</b>");
		cell("description").find("b").should("not.exist");
	});

	// Newlines must render as <br> elements, not escaped text.
	it("renders newlines as <br> in Small Text cell", () => {
		newDoc("Newlines");
		addRow({ title: ["row1", "Data"], notes: ["line1{enter}line2", "Small Text"] });
		cell("notes").find("br").should("exist");
		cell("notes").should("contain.text", "line1").and("contain.text", "line2");
	});

	after(() => {
		cy.go_to_list(PARENT);
		cy.get("body").then(($body) => {
			if ($body.find(".list-row-checkbox").length) {
				cy.get(".list-row-checkbox").each(($el) => cy.wrap($el).click({ force: true }));
				cy.get(".actions-btn-group > .btn").contains("Actions").click();
				cy.get('.actions-btn-group > .dropdown-menu [data-label="Delete"]').click();
				cy.click_modal_primary_button("Yes");
			}
		});
	});
});
