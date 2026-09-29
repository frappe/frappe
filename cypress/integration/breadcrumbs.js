// The trail is page-scoped: a page holds its own crumbs and paints them into its own head.
// These assert what the reader sees, and that a view cannot write to a page it does not own.
const CRUMBS = ".navbar-breadcrumbs:visible li";

function trail() {
	return cy.get(CRUMBS).then(($li) => Cypress._.map($li, (li) => li.textContent.trim()));
}

// the same read, from inside a cy.window(); the container's page is the visible one, so this
// needs no `:visible` and stays a plain CSS selector
function trail_of(win) {
	return Cypress._.map(
		win.frappe.container.page.querySelectorAll(".navbar-breadcrumbs li"),
		(li) => li.textContent.trim()
	);
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

	// the old module's members are kept so an app written against them keeps running
	it("warns and does nothing for the members it retired", () => {
		cy.visit("/desk/todo");
		cy.desk_ready();
		// `trail_of` reads once with no retry, so wait for the bar to be painted first
		trail().should("deep.equal", ["To Do"]);

		cy.window().then((win) => {
			cy.stub(win.console, "warn").as("warn");

			const before = trail_of(win);
			const b = win.frappe.breadcrumbs;

			// none of these may throw, and none may change what is on screen
			b.clear();
			b.rename("ToDo", "old", "new");
			b.toggle(true);
			b.append_breadcrumb_element("/desk/nowhere", "Nowhere");
			b.set_custom_breadcrumbs({ label: "Nowhere", route: "/desk/nowhere" });
			b.set_tree_breadcrumb({ doctype: "ToDo" });
			b.set_list_breadcrumb({ doctype: "ToDo" });
			b.set_form_breadcrumb({ doctype: "ToDo" }, "form");
			b.set_dashboard_breadcrumb({ doctype: "Dashboard" });
			b.current_page();

			// `all` was read and written by route, and `$breadcrumbs` was appended to
			b.all["List/ToDo/List"] = { doctype: "ToDo" };
			expect(b.all["List/ToDo/List"]).to.deep.equal({ doctype: "ToDo" });
			b.$breadcrumbs.append("<li><a>Nowhere</a></li>");

			expect(trail_of(win)).to.deep.equal(before);
		});

		cy.get("@warn").should("have.been.called");
		trail().should("deep.equal", ["To Do"]);
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
