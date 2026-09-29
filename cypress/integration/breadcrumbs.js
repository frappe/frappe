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

	// the old module still works, rather than merely not throwing: each member forwards to the
	// page on screen
	it("still draws through the retired API", () => {
		cy.visit("/desk/todo");
		cy.desk_ready();
		trail().should("deep.equal", ["To Do"]);

		cy.window().then((win) => {
			cy.stub(win.console, "warn").as("warn");
			const b = win.frappe.breadcrumbs;

			expect(win.frappe.get_current_page()).to.equal(win.frappe.container.page.page);

			b.clear();
			expect(trail_of(win)).to.deep.equal([]);

			// the shape workflow_builder used: empty the bar, then append markup by hand
			b.$breadcrumbs.append('<li><a href="/desk/workflow">Workflow</a></li>');
			expect(trail_of(win)).to.deep.equal(["Workflow"]);

			b.clear();
			b.append_breadcrumb_element("/desk/todo", "To Do");
			b.set_custom_breadcrumbs({ label: "Custom", route: "/desk/x" });
			expect(trail_of(win)).to.deep.equal(["To Do", "Custom"]);

			b.clear();
			b.set_list_breadcrumb({ doctype: "ToDo" });
			expect(trail_of(win)).to.deep.equal(["ToDo"]);

			// appending after add() keeps what add() drew: that trail is held as an
			// unresolved payload, so reading the items directly would drop it
			b.clear();
			b.add({ type: "Custom", label: "Print Format", route: "/desk/print-format" });
			expect(trail_of(win)).to.deep.equal(["Print Format"]);
			b.append_breadcrumb_element("", "Standard");
			expect(trail_of(win)).to.deep.equal(["Print Format", "Standard"]);
			b.append_breadcrumb_element("", "Third");
			expect(trail_of(win)).to.deep.equal(["Print Format", "Standard", "Third"]);

			b.clear();
			b.set_list_breadcrumb({ doctype: "ToDo" });

			// toggle hides and shows, where it used to set a class no stylesheet read
			b.toggle(false);
			expect(trail_of(win)).to.deep.equal([]);
			b.toggle(true);
			expect(trail_of(win)).to.deep.equal(["ToDo"]);

			// the registry shape: write the source, then repaint
			b.clear();
			b.all[win.frappe.get_route_str()] = { module: "Desk", doctype: "ToDo" };
			b.update();
			expect(trail_of(win)).to.deep.equal(["ToDo"]);

			expect(b.current_page()).to.equal("List/ToDo/List");
		});

		cy.get("@warn").should("have.been.called");
	});

	// the compat layer resolves to a page, never to a selector, so it cannot reach a page it is
	// not on
	it("cannot reach a page that is not on screen through the retired API", () => {
		cy.visit("/desk/todo");
		cy.desk_ready();
		trail().should("deep.equal", ["To Do"]);

		cy.window().then((win) => {
			const detached = win.$("<div>");
			const off_screen = win.frappe.ui.make_app_page({
				parent: detached,
				single_column: true,
			});
			off_screen.set_breadcrumbs([{ label: "Off screen" }]);

			win.frappe.breadcrumbs.clear();
			win.frappe.breadcrumbs.append_breadcrumb_element("/desk/x", "Landed here");

			// the visible page took the write; the off-screen one kept its own
			expect(trail_of(win)).to.deep.equal(["Landed here"]);
			expect(
				Cypress._.map(detached.find(".navbar-breadcrumbs li"), (l) => l.textContent.trim())
			).to.deep.equal(["Off screen"]);
		});
	});

	// a form embedded in a dialog has a page head of its own. It must not draw a trail there,
	// and it must not touch the trail of the page the dialog opened over.
	it("draws no trail for a form inside a dialog", () => {
		cy.visit("/desk/todo");
		cy.desk_ready();
		trail().should("deep.equal", ["To Do"]);

		cy.window().then((win) => {
			return new Promise((resolve) => {
				win.frappe.model.with_doctype("ToDo", () => {
					const dialog = new win.frappe.ui.Dialog({ title: "probe" });
					const $host = win.$("<div>").appendTo(dialog.$body);
					dialog.show();

					const frm = new win.frappe.ui.form.Form("ToDo", $host.get(0), false);
					frm.in_dialog = true;
					frm.refresh(win.frappe.model.make_new_doc_and_get_name("ToDo"));

					setTimeout(() => {
						expect($host.find(".navbar-breadcrumbs li")).to.have.length(0);
						dialog.hide();
						resolve();
					}, 800);
				});
			});
		});

		// the page underneath is untouched
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
