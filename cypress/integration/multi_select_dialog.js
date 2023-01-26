context("MultiSelectDialog", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
		const contact_template = {
			doctype: "Contact",
			first_name: "Test",
			status: "Passive",
			email_ids: [
				{
					doctype: "Contact Email",
					email_id: "test@example.com",
					is_primary: 0,
				},
			],
		};
		const promises = Array.from({ length: 25 }).map(() =>
			cy.insert_doc("Contact", contact_template, true)
		);
		Promise.all(promises);
	});

	function open_multi_select_dialog() {
		cy.window()
			.its("frappe")
			.then((frappe) => {
				new frappe.ui.form.MultiSelectDialog({
					doctype: "Contact",
					target: {},
					setters: {
						status: null,
						gender: null,
					},
					add_filters_group: 1,
					allow_child_item_selection: 1,
					child_fieldname: "email_ids",
					child_columns: ["email_id", "is_primary"],
				});
			});
	}

	it("checks multi select dialog api works", () => {
		open_multi_select_dialog();
		cy.get_open_dialog().should("contain", "Select Contacts");
	});

	it("checks for filters", () => {
		["search_term", "status", "gender"].forEach((fieldname) => {
			cy.get_open_dialog()
				.get(`.frappe-control[data-fieldname="${fieldname}"]`)
				.should("exist");
		});

		// add_filters_group: 1 should add a filter group
		cy.get_open_dialog().get(`.frappe-control[data-fieldname="filter_area"]`).should("exist");
	});

	it("checks for child item selection", () => {
		cy.get_open_dialog().get(`.dt-row-header`).should("not.exist");

		cy.get_open_dialog()
			.get(`.frappe-control[data-fieldname="allow_child_item_selection"]`)
			.find('input[data-fieldname="allow_child_item_selection"]')
			.should("exist")
			.click({ force: true });

		cy.get_open_dialog()
			.get(`.frappe-control[data-fieldname="child_selection_area"]`)
			.should("exist");

		cy.get_open_dialog().get(`.dt-row-header`).should("contain", "Contact");

		cy.get_open_dialog().get(`.dt-row-header`).should("contain", "Email Id");

		cy.get_open_dialog().get(`.dt-row-header`).should("contain", "Is Primary");
	});

	it("tests more button", () => {
		cy.get_open_dialog()
			.get(`.frappe-control[data-fieldname="more_child_btn"]`)
			.should("exist")
			.as("more-btn");

		cy.get_open_dialog()
			.get(".datatable .dt-scrollable .dt-row")
			.should(($rows) => {
				expect($rows).to.have.length(20);
			});

		cy.intercept("POST", "api/method/frappe.client.get_list").as("get-more-records");
		cy.get("@more-btn").find("button").click({ force: true });
		cy.wait("@get-more-records");

		cy.get_open_dialog()
			.get(".datatable .dt-scrollable .dt-row")
			.should(($rows) => {
				if ($rows.length <= 20) {
					throw new Error("More button doesn't work");
				}
			});
	});
});
