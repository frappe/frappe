import doctype_with_child_table from "../fixtures/doctype_with_child_table";
import child_table_doctype from "../fixtures/child_table_doctype";
import child_table_doctype_1 from "../fixtures/child_table_doctype_1";
import doctype_to_link from "../fixtures/doctype_to_link";
const doctype_to_link_name = doctype_to_link.name;
const child_table_doctype_name = child_table_doctype.name;

context("Dashboard links", () => {
	before(() => {
		cy.visit("/login");
		cy.login("Administrator");
		cy.insert_doc("DocType", child_table_doctype, true);
		cy.insert_doc("DocType", child_table_doctype_1, true);
		cy.insert_doc("DocType", doctype_with_child_table, true);
		cy.insert_doc("DocType", doctype_to_link, true);
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				frappe.call("frappe.tests.ui_test_helpers.update_child_table", {
					name: child_table_doctype_name,
				});
			});
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
});
