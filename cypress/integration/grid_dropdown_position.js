context("Grid dropdown position", () => {
	before(() => {
		cy.login("Administrator");
		cy.visit("/desk/");
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.xcall(
					"frappe.tests.ui_test_helpers.create_webform_with_child_table_dropdown"
				);
			});
	});

	it("draws the child table dropdown next to the field on a scrolled web form", () => {
		cy.visit("/test-grid-dropdown/new");

		const cell = '.grid-body .rows .grid-row .col[data-fieldname="item"]';
		cy.get(".grid-add-row").click();
		cy.get(cell).first().click();
		cy.get(`${cell} input`).first().type("a");
		cy.get(".awesomplete > ul:visible li").should("be.visible");

		// the dropdown is positioned by hand, and used to be displaced by the page scroll
		cy.window().its("scrollY").should("be.greaterThan", 100);

		cy.get(`${cell} input`)
			.first()
			.then(($input) => {
				cy.get(".awesomplete > ul:visible").then(($list) => {
					const gap =
						$list[0].getBoundingClientRect().top -
						$input[0].getBoundingClientRect().bottom;
					expect(gap, "gap between field and dropdown").to.be.within(-20, 20);
				});
			});
	});
});
