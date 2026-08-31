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

	it("shows Expand All / Collapse All only when the tree's state warrants it", () => {
		cy.visit("/app/custom-tree/view/tree");

		// both actions live in one dropdown; the menu resolves fresh on every
		// open, disabling whichever action doesn't apply right now. Rows are
		// real <button disabled> elements per the es-menu contract.
		const toggle_menu = () => cy.get(".tree-toolbar-actions .es-button").first().click();
		const assert_buttons = (expand_enabled, collapse_enabled) => {
			toggle_menu();
			cy.contains('[role="menu"] .es-menu__item', "Expand All").should(
				expand_enabled ? "not.be.disabled" : "be.disabled"
			);
			cy.contains('[role="menu"] .es-menu__item', "Collapse All").should(
				collapse_enabled ? "not.be.disabled" : "be.disabled"
			);
			toggle_menu();
		};
		const click_toolbar_button = (label) => {
			toggle_menu();
			cy.contains('[role="menu"] .es-menu__item', label).click();
		};

		// root auto-expands; both groups underneath are still collapsed -> only "Expand All"
		assert_buttons(true, false);

		// expand one group, leave its sibling group collapsed -> partially
		// expanded, so both buttons offer their one-click action
		cy.get('.tree-link[data-label="Parent Node"]').click();
		cy.get('.tree-link[data-label="Child Node"]').should("be.visible");
		assert_buttons(true, true);

		// Expand All -> every node, including the untouched sibling group, opens -> only "Collapse All"
		click_toolbar_button("Expand All");
		cy.get('.tree-link[data-label="Child Node"]').should("be.visible");
		assert_buttons(false, true);

		// collapsing the root hides every descendant; only "Expand All" should be
		// offered, regardless of the (now hidden) descendants' own expanded flags
		cy.get('.tree-link[data-label="All Trees"]').click();
		cy.get('.tree-link[data-label="Parent Node"]').should("not.be.visible");
		assert_buttons(true, false);

		// reopening the root restores the descendants exactly as they were left,
		// so the mixed/all-expanded state from before is visible again
		cy.get('.tree-link[data-label="All Trees"]').click();
		cy.get('.tree-link[data-label="Child Node"]').should("be.visible");
		assert_buttons(false, true);

		// Collapse All -> back to the initial state
		click_toolbar_button("Collapse All");
		cy.get('.tree-link[data-label="Child Node"]').should("not.exist");
		assert_buttons(true, false);
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
