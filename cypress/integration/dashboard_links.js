import doctype_with_child_table from "../fixtures/doctype_with_child_table";
import child_table_doctype from "../fixtures/child_table_doctype";
import child_table_doctype_1 from "../fixtures/child_table_doctype_1";
import doctype_to_link from "../fixtures/doctype_to_link";

import doctype_a_with_child_table_with_link_to_doctype_b from "../fixtures/doctype_a_with_child_table_with_link_to_doctype_b";
import doctype_a_with_child_table_with_link_to_doctype_b_dashboard from "../fixtures/doctype_a_with_child_table_with_link_to_doctype_b_dashboard";
import doctype_b_with_child_table_with_link_to_doctype_a from "../fixtures/doctype_b_with_child_table_with_link_to_doctype_a";
import child_table_with_link_to_doctype_a from "../fixtures/child_table_with_link_to_doctype_a";
import child_table_with_link_to_doctype_b from "../fixtures/child_table_with_link_to_doctype_b";

const doctype_to_link_name = doctype_to_link.name;
const child_table_doctype_name = child_table_doctype.name;
const doctype_a_with_child_table_with_link_to_doctype_b_name =
	doctype_a_with_child_table_with_link_to_doctype_b.name;
const doctype_b_with_child_table_with_link_to_doctype_a_name =
	doctype_b_with_child_table_with_link_to_doctype_a.name;
const child_table_with_link_to_doctype_a_name = child_table_with_link_to_doctype_a.name;
const child_table_with_link_to_doctype_b_name = child_table_with_link_to_doctype_b.name;

context("Dashboard links", () => {
	before(() => {
		cy.visit("/login");
		cy.login("Administrator");
		cy.insert_doc("DocType", child_table_doctype, true);
		cy.insert_doc("DocType", child_table_doctype_1, true);
		cy.insert_doc("DocType", doctype_with_child_table, true);
		cy.insert_doc("DocType", doctype_to_link, true);

		cy.insert_doc("DocType", child_table_with_link_to_doctype_a, true);
		cy.insert_doc("DocType", child_table_with_link_to_doctype_b, true);
		cy.insert_doc("DocType", doctype_a_with_child_table_with_link_to_doctype_b, true);
		cy.insert_doc("DocType", doctype_b_with_child_table_with_link_to_doctype_a, true);

		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				frappe.run_serially([
					() =>
						frappe.call("frappe.tests.ui_test_helpers.update_child_table", {
							name: child_table_doctype_name,
						}),
					() =>
						frappe.call("frappe.tests.ui_test_helpers.update_child_table", {
							name: child_table_with_link_to_doctype_a_name,
							doctype_to_link_name:
								"Doctype A With Child Table With Link To Doctype B",
							doctype_to_link_fieldname:
								"doctype_a_with_child_table_with_link_to_doctype_b",
						}),
					() =>
						frappe.call(
							"frappe.tests.ui_test_helpers.create_dashboard_py_for_doctype",
							{
								name: doctype_a_with_child_table_with_link_to_doctype_b_name,
								dashboard:
									doctype_a_with_child_table_with_link_to_doctype_b_dashboard,
							}
						),
					() =>
						frappe.call("frappe.tests.ui_test_helpers.update_child_table", {
							name: child_table_with_link_to_doctype_b_name,
							doctype_to_link_name:
								"Doctype B With Child Table With Link To Doctype A",
							doctype_to_link_fieldname:
								"doctype_b_with_child_table_with_link_to_doctype_a",
						}),
				]);
			});
	});

	after(() => {
		cy.remove_doc("DocType", child_table_with_link_to_doctype_a_name);
		cy.remove_doc("DocType", child_table_with_link_to_doctype_b_name);
		cy.remove_doc("DocType", doctype_a_with_child_table_with_link_to_doctype_b_name);
		cy.remove_doc("DocType", doctype_b_with_child_table_with_link_to_doctype_a_name);
	});

	it("Adding a new contact, checking for the counter on the dashboard and deleting the created contact", () => {
		cy.visit("/app/contact");
		cy.clear_filters();

		cy.visit(`/app/user/${cy.config("testUser")}`);

		//To check if initially the dashboard contains only the "Contact" link and there is no counter
		cy.select_form_tab("Connections");
		cy.get('[data-doctype="Contact"]').should("contain", "Contact");

		//Adding a new contact
		cy.get('.document-link-badge[data-doctype="Contact"]').click();
		cy.wait(300);
		cy.findByRole("button", { name: "Add Contact" }).should("be.visible");
		cy.findByRole("button", { name: "Add Contact" }).click();
		cy.get('[data-doctype="Contact"][data-fieldname="first_name"]').type("Admin");
		cy.findByRole("button", { name: "Save" }).click();
		cy.visit(`/app/user/${cy.config("testUser")}`);

		//To check if the counter for contact doc is "2" after adding additional contact
		cy.select_form_tab("Connections");
		cy.get('[data-doctype="Contact"] > .count').should("contain", "2");
		cy.get('[data-doctype="Contact"]').contains("Contact").click();

		//Deleting the newly created contact
		cy.visit("/app/contact");
		cy.get(".list-subject > .select-like > .list-row-checkbox").eq(0).click({ force: true });
		cy.findByRole("button", { name: "Actions" }).click();
		cy.get('.actions-btn-group [data-label="Delete"]').click();
		cy.findByRole("button", { name: "Yes" }).click({ delay: 700 });

		//To check if the counter from the "Contact" doc link is removed
		cy.wait(700);
		cy.visit("/app/user");
		cy.get(".list-row-col > .level-item > .ellipsis").eq(0).click({ force: true });
		cy.get('[data-doctype="Contact"]').should("contain", "Contact");
	});

	it("Report link in dashboard", () => {
		cy.visit(`/app/user/${cy.config("testUser")}`);
		cy.select_form_tab("Connections");
		cy.get('.document-link[data-doctype="Contact"]').contains("Contact");
		cy.window()
			.its("cur_frm")
			.then((cur_frm) => {
				cur_frm.dashboard.data.reports = [
					{
						label: "Reports",
						items: ["Website Analytics"],
					},
				];
				cur_frm.dashboard.render_report_links();
				cy.get('.document-link[data-report="Website Analytics"]')
					.contains("Website Analytics")
					.click();
			});
	});

	it("check if child table is populated with linked field on creation from dashboard link", () => {
		cy.new_form(doctype_to_link_name);
		cy.fill_field("title", "Test Linking");
		cy.findByRole("button", { name: "Save" }).click();

		cy.get(".document-link .btn-new").click();
		cy.get(
			'.frappe-control[data-fieldname="child_table"] .rows .data-row .col[data-fieldname="doctype_to_link"]'
		).should("contain.text", "Test Linking");
	});

	it("Adds a new doctype_b_with_child_table_with_link_to_doctype_a and a new doctype_a_with_child_table_with_link_to_doctype_b with a link to the previous doc, checks for the counter on the doctype_a_with_child_table_with_link_to_doctype_b's dashboard and deletes the created docs", () => {
		//Adding a new Doctype B With Child Table With Link To Doctype A
		cy.visit("/app/doctype-b-with-child-table-with-link-to-doctype-a");
		cy.clear_filters();
		cy.findByRole("button", {
			name: "Add Doctype B With Child Table With Link To Doctype A",
		}).should("be.visible");
		cy.findByRole("button", {
			name: "Add Doctype B With Child Table With Link To Doctype A",
		}).click();
		cy.get(
			'[data-doctype="Doctype B With Child Table With Link To Doctype A"][data-fieldname="title"]'
		).type("Earth");
		cy.get('.frappe-control[data-fieldname="child_table"]').as("table");
		cy.get("@table").findByRole("button", { name: "Add Row" }).click();
		cy.get("@table").find('[data-idx="1"]').as("row1");
		cy.get("@row1").find(".btn-open-row").click();
		cy.get("@row1").find(".form-in-grid").as("row1-form_in_grid");
		cy.fill_table_field("child_table", "1", "title", "Earth");
		cy.get("@row1-form_in_grid").find(".grid-collapse-row").click();
		cy.findByRole("button", { name: "Save" }).click();

		//Adding a new Doctype A With Child Table With Link To Doctype B with a link to the previous doc
		cy.visit("/app/doctype-a-with-child-table-with-link-to-doctype-b");
		cy.clear_filters();
		cy.findByRole("button", {
			name: "Add Doctype A With Child Table With Link To Doctype B",
		}).should("be.visible");
		cy.findByRole("button", {
			name: "Add Doctype A With Child Table With Link To Doctype B",
		}).click();
		cy.get(
			'[data-doctype="Doctype A With Child Table With Link To Doctype B"][data-fieldname="title"]'
		).type("Mars");
		cy.get('.frappe-control[data-fieldname="child_table"]').as("table");
		cy.get("@table").findByRole("button", { name: "Add Row" }).click();
		cy.get("@table").find('[data-idx="1"]').as("row1");
		cy.get("@row1").find(".btn-open-row").click();
		cy.get("@row1").find(".form-in-grid").as("row1-form_in_grid");
		cy.fill_table_field("child_table", "1", "title", "Mars");
		cy.fill_table_field(
			"child_table",
			"1",
			"doctype_b_with_child_table_with_link_to_doctype_a",
			"Earth"
		);
		cy.get("@row1-form_in_grid").find(".grid-collapse-row").click();
		cy.findByRole("button", { name: "Save" }).click();

		//To check if the counter for Doctype B With Child Table With Link To Doctype A is 1
		cy.visit(`/app/doctype-a-with-child-table-with-link-to-doctype-b/Mars`);
		cy.get(".form-tabs > .nav-item").eq(1).click();
		cy.get(
			'[data-doctype="Doctype B With Child Table With Link To Doctype A"] > .count'
		).should("contain", "1");
		cy.get('[data-doctype="Doctype B With Child Table With Link To Doctype A"]')
			.contains("Doctype B With Child Table With Link To Doctype A")
			.click();

		//Deleting the newly created docs
		cy.visit("/app/doctype-a-with-child-table-with-link-to-doctype-b");
		cy.get(".list-subject > .select-like > .list-row-checkbox").eq(0).click({ force: true });
		cy.findByRole("button", { name: "Actions" }).click();
		cy.get('.actions-btn-group [data-label="Delete"]').click();
		cy.findByRole("button", { name: "Yes" }).click({ delay: 700 });
		cy.visit("/app/doctype-b-with-child-table-with-link-to-doctype-a");
		cy.get(".list-subject > .select-like > .list-row-checkbox").eq(0).click({ force: true });
		cy.findByRole("button", { name: "Actions" }).click();
		cy.get('.actions-btn-group [data-label="Delete"]').click();
		cy.findByRole("button", { name: "Yes" }).click({ delay: 700 });
	});

	it("Adds a new doctype_a_with_child_table_with_link_to_doctype_b and a new doctype_b_with_child_table_with_link_to_doctype_a with a link to the previous doc, checks for the counter on the doctype_a_with_child_table_with_link_to_doctype_b's dashboard and deletes the created docs", () => {
		//Adding a new Doctype A With Child Table With Link To Doctype B
		cy.visit("/app/doctype-a-with-child-table-with-link-to-doctype-b");
		cy.clear_filters();
		cy.findByRole("button", {
			name: "Add Doctype A With Child Table With Link To Doctype B",
		}).should("be.visible");
		cy.findByRole("button", {
			name: "Add Doctype A With Child Table With Link To Doctype B",
		}).click();
		cy.get(
			'[data-doctype="Doctype A With Child Table With Link To Doctype B"][data-fieldname="title"]'
		).type("Neptune");
		cy.get('.frappe-control[data-fieldname="child_table"]').as("table");
		cy.get("@table").findByRole("button", { name: "Add Row" }).click();
		cy.get("@table").find('[data-idx="1"]').as("row1");
		cy.get("@row1").find(".btn-open-row").click();
		cy.get("@row1").find(".form-in-grid").as("row1-form_in_grid");
		cy.fill_table_field("child_table", "1", "title", "Neptune");
		cy.get("@row1-form_in_grid").find(".grid-collapse-row").click();
		cy.findByRole("button", { name: "Save" }).click();

		//Adding a new Doctype B With Child Table With Link To Doctype A with a link to the previous doc
		cy.visit("/app/doctype-b-with-child-table-with-link-to-doctype-a");
		cy.clear_filters();
		cy.findByRole("button", {
			name: "Add Doctype B With Child Table With Link To Doctype A",
		}).should("be.visible");
		cy.findByRole("button", {
			name: "Add Doctype B With Child Table With Link To Doctype A",
		}).click();
		cy.get(
			'[data-doctype="Doctype B With Child Table With Link To Doctype A"][data-fieldname="title"]'
		).type("Pluto");
		cy.get('.frappe-control[data-fieldname="child_table"]').as("table");
		cy.get("@table").findByRole("button", { name: "Add Row" }).click();
		cy.get("@table").find('[data-idx="1"]').as("row1");
		cy.get("@row1").find(".btn-open-row").click();
		cy.get("@row1").find(".form-in-grid").as("row1-form_in_grid");
		cy.fill_table_field("child_table", "1", "title", "Pluto");
		cy.fill_table_field(
			"child_table",
			"1",
			"doctype_a_with_child_table_with_link_to_doctype_b",
			"Neptune"
		);
		cy.get("@row1-form_in_grid").find(".grid-collapse-row").click();
		cy.findByRole("button", { name: "Save" }).click();

		//To check if the counter for Doctype B With Child Table With Link To Doctype A is 1
		cy.visit(`/app/doctype-a-with-child-table-with-link-to-doctype-b/Neptune`);
		cy.get(".form-tabs > .nav-item").eq(1).click();
		cy.get(
			'[data-doctype="Doctype B With Child Table With Link To Doctype A"] > .count'
		).should("contain", "1");
		cy.get('[data-doctype="Doctype B With Child Table With Link To Doctype A"]')
			.contains("Doctype B With Child Table With Link To Doctype A")
			.click();

		//Deleting the newly created docs
		cy.visit("/app/doctype-a-with-child-table-with-link-to-doctype-b");
		cy.get(".list-subject > .select-like > .list-row-checkbox").eq(0).click({ force: true });
		cy.findByRole("button", { name: "Actions" }).click();
		cy.get('.actions-btn-group [data-label="Delete"]').click();
		cy.findByRole("button", { name: "Yes" }).click({ delay: 700 });
		cy.visit("/app/doctype-b-with-child-table-with-link-to-doctype-a");
		cy.get(".list-subject > .select-like > .list-row-checkbox").eq(0).click({ force: true });
		cy.findByRole("button", { name: "Actions" }).click();
		cy.get('.actions-btn-group [data-label="Delete"]').click();
		cy.findByRole("button", { name: "Yes" }).click({ delay: 700 });
	});
});
