context("Tree View", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.call("frappe.tests.ui_test_helpers.setup_tree_doctype");
	});

	it("keeps expanded nodes when navigating back to the tree", () => {
		cy.visit("/app/custom-tree/view/tree");

		// root auto-expands; expand the parent to load its child
		cy.get('.tree-link[data-label="Parent Node"]').click();
		cy.get('.tree-link[data-label="Child Node"]').should("be.visible");

		// leave the tree, then return with the browser back button
		cy.window().then((win) => win.frappe.set_route("List", "ToDo"));
		cy.get('[data-page-route="Tree/Custom Tree"]').should("not.be.visible");

		cy.go("back");
		cy.get('[data-page-route="Tree/Custom Tree"]').should("be.visible");
		cy.get('.tree-link[data-label="Child Node"]').should("be.visible");

		cy.window()
			.its("cur_tree")
			.then((tree) => {
				expect(tree.nodes["Parent Node"].expanded).to.be.true;
			});
	});

	it("restores the scroll position when navigating back to the tree", () => {
		cy.visit("/app/custom-tree/view/tree");

		// root auto-expands; scroll a deep node into view to move the page down
		cy.get('.tree-link[data-label="Scroll Node 39"]').scrollIntoView();
		cy.get(".main-section")
			.its("0.scrollTop")
			.should("be.gt", 0)
			.then((scroll_position) => {
				cy.window().then((win) => win.frappe.set_route("List", "ToDo"));
				cy.get('[data-page-route="Tree/Custom Tree"]').should("not.be.visible");

				cy.go("back");
				cy.get('[data-page-route="Tree/Custom Tree"]').should("be.visible");
				cy.get(".main-section").its("0.scrollTop").should("eq", scroll_position);
			});
	});
});
