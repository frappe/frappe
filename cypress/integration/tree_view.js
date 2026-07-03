context("Tree View", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.call("frappe.tests.ui_test_helpers.setup_tree_doctype");
	});

	it("keeps expanded nodes when navigating back to the tree", () => {
		cy.visit("/app/custom-tree/view/tree");

		let tree_route;
		cy.window().then((win) => {
			tree_route = win.frappe.get_route();
		});

		// root auto-expands; expand the parent to load its child
		cy.get('.tree-link[data-label="Parent Node"]').click();
		cy.get('.tree-link[data-label="Child Node"]').should("be.visible");

		// navigate away; wait until the tree page is actually hidden before returning,
		// otherwise the two route changes race and the tree may never settle back
		cy.window().then((win) => win.frappe.set_route("List", "ToDo"));
		cy.get('[data-page-route="Tree/Custom Tree"]').should("not.be.visible");

		cy.window().then((win) => win.frappe.set_route(tree_route));
		cy.get('[data-page-route="Tree/Custom Tree"]').should("be.visible");
		cy.get('.tree-link[data-label="Child Node"]').should("be.visible");
		cy.window()
			.its("cur_tree")
			.then((tree) => {
				expect(tree.nodes["Parent Node"].expanded).to.be.true;
			});
	});
});
