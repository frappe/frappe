import custom_submittable_doctype from "../fixtures/custom_submittable_doctype";
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
	before(() => {
		cy.login();
		cy.visit("/desk/todo/view/list");
	});

	it("hides the report view and redirects its route to the list view", () => {
		cy.window()
			.its("frappe")
			.then((frappe) => {
				frappe.boot.user.can_get_report = frappe.boot.user.can_get_report.filter(
					(doctype) => doctype !== "ToDo"
				);
			});

		cy.get(".custom-btn-group.view-switcher button").click();
		cy.get(".es-menu[data-state='open']")
			.should("contain", "Dashboard View")
			.and("not.contain", "Report View");
		cy.focused().trigger("keydown", { key: "Escape" });

		cy.window()
			.its("frappe")
			.then((frappe) => frappe.set_route("List", "ToDo", "Report"));
		cy.window().its("cur_list.view_name").should("equal", "List");
		cy.location("pathname").should("not.contain", "report");
	});
});
