import custom_submittable_doctype from "../fixtures/custom_submittable_doctype";
import doctype_without_report_permission from "../fixtures/doctype_without_report_permission";
const doctype_name = custom_submittable_doctype.name;

context("Report View", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.insert_doc("DocType", custom_submittable_doctype, true);
		cy.clear_cache();
		cy.insert_doc(
			doctype_name,
			{
				title: "Doc 1",
				description: "Random Text",
				enabled: 0,
				docstatus: 1, // submit document
			},
			true
		);
	});

	it("Field with enabled allow_on_submit should be editable.", () => {
		cy.intercept("POST", "api/method/frappe.client.set_value").as("value-update");
		cy.visit(`/desk/List/${doctype_name}/Report`);

		// check status column added from docstatus
		cy.get(".dt-row-0 > .dt-cell--col-3").should("contain", "Submitted");
		let cell = cy.get(".dt-row-0 > .dt-cell--col-4");

		// select the cell
		cell.dblclick();
		cell.get(".dt-cell__edit--col-4").findByRole("checkbox").check({ force: true });
		cy.get(".dt-row-0 > .dt-cell--col-3").click(); // click outside

		cy.wait("@value-update");

		cy.call("frappe.client.get_value", {
			doctype: doctype_name,
			filters: {
				title: "Doc 1",
			},
			fieldname: "enabled",
		}).then((r) => {
			expect(r.message.enabled).to.equals(1);
		});
	});
});

context("Report View without report permission", () => {
	const test_user = "test_report_permission@example.com";
	const list_route = "/desk/doctype-without-report-permission";

	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.insert_doc("Role", { role_name: "Report Permission Test Role", desk_access: 1 }, true);
		cy.insert_doc("DocType", doctype_without_report_permission, true);
		cy.clear_cache();
		cy.call("frappe.tests.ui_test_helpers.create_test_user", { username: test_user });
		cy.switch_to_user(test_user);
	});

	after(() => {
		cy.switch_to_user("Administrator");
	});

	it("hides the report view and redirects its route to the list view", () => {
		cy.visit(`${list_route}/view/list`);

		cy.get(".custom-btn-group.view-switcher button").click();
		cy.get(".es-menu[data-state='open']")
			.should("contain", "Dashboard View")
			.and("not.contain", "Report View");
		cy.focused().trigger("keydown", { key: "Escape" });

		cy.visit(`${list_route}/view/report`);
		cy.window().its("cur_list.view_name").should("equal", "List");
		cy.location("pathname").should("not.contain", "/view/report");
	});

	it("opens the list view when the doctype defaults to the report view", () => {
		cy.visit(list_route);
		cy.window().its("cur_list.view_name").should("equal", "List");
		cy.get(".title-text").should("contain", "DocType Without Report Permission");
	});
});
