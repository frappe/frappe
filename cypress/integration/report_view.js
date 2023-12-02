import custom_submittable_doctype from "../fixtures/custom_submittable_doctype";
const doctype_name = custom_submittable_doctype.name;

context("Report View", () => {
	before(() => {
		cy.login();
		cy.visit("/app/website");
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
		cy.visit(`/app/List/${doctype_name}/Report`);

		// Find the row with 'Doc 1' and check status column added from docstatus.
		cy.findByText("Doc 1").parents(".dt-row").as("target_row");
		cy.get("@target_row").find(".dt-cell--col-3").should("contain", "Submitted");

		// Doubleclick to edit the cell and tick 'enabled'.
		cy.get("@target_row").find(".dt-cell--col-4").as("cell");
		cy.get("@cell").dblclick();
		cy.get("@cell").get(".dt-cell__edit--col-4").findByRole("checkbox").check({ force: true });

		// Click outside to trigger save and wait for the POST request to complete.
		cy.get("@target_row").find(".dt-cell--col-3").click();
		cy.wait("@value-update");

		// Verify that the 'enabled' field is updated.
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
