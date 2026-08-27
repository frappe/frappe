context("Website Analytics", () => {
	const linked_source = "Web Page <b>newsletter</b>";
	const plain_source = "newsletter <b";
	const campaign = "spring sale <b";

	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.insert_doc(
			"Web Page View",
			{ path: "blog/introducing-frappe-framework-v16", source: linked_source },
			true
		);
		cy.insert_doc(
			"Web Page View",
			{ path: "blog/scaling-frappe-in-production", source: plain_source },
			true
		);
		cy.insert_doc(
			"Web Page View",
			{ path: "blog/whats-new-in-erpnext", campaign: campaign },
			true
		);
	});

	function group_by(label) {
		cy.visit("/desk/query-report/Website Analytics");
		cy.get(".datatable", { timeout: 60000 }).should("exist");
		cy.get('#page-query-report select[data-fieldname="group_by"]').select(label, {
			force: true,
		});
	}

	it("renders the source column as text", () => {
		group_by("Source");

		cy.contains(".dt-cell__content", linked_source).should("exist");
		cy.contains(".dt-cell__content", plain_source).should("exist");
		cy.get(".datatable .dt-cell__content").find("b").should("not.exist");
	});

	it("renders the campaign column as text", () => {
		group_by("Campaign");

		cy.contains(".dt-cell__content", campaign).should("exist");
		cy.get(".datatable .dt-cell__content").find("b").should("not.exist");
	});
});
