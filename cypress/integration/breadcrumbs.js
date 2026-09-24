// The trail is page-scoped: a page holds its own crumbs and paints them into its own head.
// These assert what the reader sees, and that a view cannot write to a page it does not own.
const CRUMBS = ".navbar-breadcrumbs:visible li";

function trail() {
	return cy.get(CRUMBS).then(($li) => Cypress._.map($li, (li) => li.textContent.trim()));
}

context("Breadcrumbs", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.call("frappe.tests.ui_test_helpers.setup_tree_doctype");
	});

	it("names a list once", () => {
		cy.visit("/desk/todo");
		cy.desk_ready();
		trail().should("deep.equal", ["To Do"]);
	});

	it("leads a document back to its list", () => {
		cy.insert_doc("ToDo", { description: "crumb test todo" }, true).then((doc) => {
			cy.visit(`/desk/todo/${doc.name}`);
			cy.desk_ready();
			cy.get(CRUMBS).first().find("a").should("have.attr", "href", "/desk/todo");
			cy.get(CRUMBS).last().find("a").should("not.exist");
		});
	});

	// the list crumb and the title used to be the same node, and whichever of
	// `set_list_breadcrumb` and `page.set_title` ran last won it: this route rendered
	// `ToDo / ToDo`, with the first crumb still linking to the DocType list
	it("does not repeat the document name over its doctype", () => {
		cy.visit("/desk/doctype/ToDo");
		cy.desk_ready();
		trail().should("deep.equal", ["DocType", "ToDo"]);
	});

	// a doctype whose desk page is not its form: the old renderer read the route's first
	// segment, so `print-format-builder` matched no branch and drew an empty bar
	it("names a doctype that has a page of its own", () => {
		cy.insert_doc(
			"Print Format",
			{ name: "Crumb Format", doc_type: "ToDo", standard: "No" },
			true
		);
		cy.visit("/desk/print-format-builder/Crumb Format");
		cy.desk_ready();
		trail().should("deep.equal", ["Print Format", "Crumb Format"]);
	});

	it("keeps the document reachable from the print view", () => {
		cy.insert_doc("ToDo", { description: "crumb print todo" }, true).then((doc) => {
			cy.visit(`/desk/print/ToDo/${doc.name}`);
			cy.desk_ready();
			cy.get(CRUMBS).should("have.length", 3);
			cy.get(CRUMBS).last().should("contain.text", "Print");
			cy.get(CRUMBS).eq(1).find("a").should("have.attr", "href", `/desk/todo/${doc.name}`);
		});
	});

	it("names a tree by its tree title", () => {
		cy.visit("/desk/custom-tree/view/tree");
		cy.get('.tree-link[data-label="All Trees"]').should("be.visible");
		trail().should("deep.equal", ["Custom Tree Tree"]);
	});

	it("names a workspace without linking it to itself", () => {
		cy.visit("/desk/build");
		cy.desk_ready();
		cy.get(CRUMBS).should("have.length", 1).find("a").should("not.exist");
	});

	// ERPNext's POS builds an off-screen form to price its items, on a parent it hands in
	// itself. `make_app_page` gives that parent a page like any other, but it is never the
	// container's, so nothing written to it can reach the bar the reader is looking at.
	it("ignores a page that is not on screen", () => {
		cy.visit("/desk/permission-manager");
		cy.desk_ready();
		trail().should("deep.equal", ["Role Permissions Manager"]);

		cy.window().then((win) => {
			const detached = win.$("<div>");
			const off_screen = win.frappe.ui.make_app_page({
				parent: detached,
				single_column: true,
			});
			off_screen.set_breadcrumbs([
				{ label: "Sales Invoice" },
				{ label: "New Sales Invoice" },
			]);

			// it did write a trail, into its own head
			expect(
				Cypress._.map(detached.find(".navbar-breadcrumbs li"), (li) =>
					li.textContent.trim()
				)
			).to.deep.equal(["Sales Invoice", "New Sales Invoice"]);
			expect(win.frappe.container.page).to.not.equal(detached[0]);
		});

		trail().should("deep.equal", ["Role Permissions Manager"]);
	});
});
