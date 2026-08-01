context("New Kanban Board", () => {
	// Same board/route as the classic suite — the `use_new_kanban` System Setting
	// (toggled in before/after below) decides which UI renders at this URL.
	const TODO_KANBAN_URL = "/desk/todo/view/kanban/ToDo Kanban";

	const set_new_kanban = (enabled) =>
		cy.set_value("System Settings", "System Settings", { use_new_kanban: enabled ? 1 : 0 });

	// Visit the board and wait for its data. Re-visiting reboots the page, so the
	// `use_new_kanban` value set server-side is picked up (boot.py exposes it on
	// frappe.boot.sysdefaults).
	const visit_board = () => {
		cy.intercept(
			"POST",
			"**/api/method/frappe.desk.doctype.kanban_board.kanban_board.get_kanban_board_data"
		).as("kanban-board-data");
		cy.visit(TODO_KANBAN_URL);
		cy.wait("@kanban-board-data");
	};

	const visit_new_kanban = () => {
		visit_board();
		cy.get(".new-kanban-container", { timeout: 15000 }).should("exist");
		cy.get(".kn-column").should("have.length.at.least", 3);
	};

	before(() => {
		cy.login(); // Administrator — needed to write System Settings
		cy.visit("/desk");
		cy.call("frappe.tests.ui_test_helpers.ensure_todo_kanban_board");
		// A few ToDos, all default to status "Open" so the Open column has cards.
		cy.call("frappe.tests.ui_test_helpers.create_todo_records");
		set_new_kanban(true);
	});

	it("renders the new Kanban board instead of the classic one", () => {
		visit_new_kanban();
		// New engine markup is present; classic markup is not.
		cy.get(".kanban-column").should("not.exist");
		cy.get('.kn-column[data-col="Open"]').should("exist");
		cy.get('.kn-column[data-col="Closed"]').should("exist");
		cy.get(".title-text").should("contain", "ToDo Kanban");
	});

	it("shows cards with titles in the Open column", () => {
		visit_new_kanban();
		cy.get('.kn-column[data-col="Open"] .kn-card')
			.should("have.length.at.least", 1)
			.first()
			.find(".kn-card-title")
			.should("not.be.empty");
	});

	it("creates a ToDo from the primary action", () => {
		cy.intercept({ method: "POST", url: "api/method/frappe.client.save" }).as("save-todo");
		visit_new_kanban();

		// Card titles on this board are the document name, so assert on the Open
		// column's card count rather than the description text. Measured fresh each
		// attempt, so a Cypress retry stays correct.
		cy.get('.kn-column[data-col="Open"] .kn-card').then(($before) => {
			const before = $before.length;

			cy.click_listview_primary_button("Add ToDo");
			cy.fill_field("description", "New Kanban Test ToDo", "Text Editor").wait(300);
			cy.get(".modal-footer .btn-modal-primary").last().click();
			cy.wait("@save-todo");

			// The primary action uses a plain frappe.new_doc (no board integration),
			// so reload — the new ToDo (defaults to status "Open") adds one card.
			visit_new_kanban();
			cy.get('.kn-column[data-col="Open"] .kn-card', { timeout: 15000 }).should(
				"have.length",
				before + 1
			);
		});
	});

	it("opens a pre-filled create dialog when adding a card to a column", () => {
		visit_new_kanban();

		// The Closed column's inline "+ Add" should open the create flow with that
		// column's group-by value (status = Closed) pre-set on the new doc.
		cy.get('.kn-column[data-col="Closed"]').find(".kn-add-card").click({ force: true });

		cy.get_open_dialog().should("be.visible");
		cy.window().its("frappe.quick_entry").should("exist");
		cy.window().then((win) => {
			expect(win.frappe.quick_entry.doc.status).to.equal("Closed");
		});
		cy.hide_dialog();
	});

	it("moves a card to another column and persists the new order", () => {
		cy.intercept(
			"POST",
			"**/api/method/frappe.desk.doctype.kanban_board.kanban_board.update_order_for_single_card"
		).as("single-card-order");

		visit_new_kanban();
		cy.get('.kn-column[data-col="Open"] .kn-card').should("have.length.at.least", 1);

		cy.get('.kn-column[data-col="Open"] .kn-card')
			.first()
			.invoke("attr", "data-name")
			.then((name) => {
				// Pragmatic Drag and Drop uses native HTML5 DnD, which Cypress can't
				// reliably simulate — drive the same move pipeline the drop triggers.
				cy.window().then((win) =>
					win.cur_list._kanban.board.engine.applyMove(name, "Open", "Closed", 0)
				);

				cy.wait("@single-card-order");
				cy.get(`.kn-column[data-col="Closed"] .kn-card[data-name="${name}"]`).should(
					"exist"
				);
				cy.get(`.kn-column[data-col="Open"] .kn-card[data-name="${name}"]`).should(
					"not.exist"
				);
			});
	});

	it("falls back to the classic Kanban board when the setting is disabled", () => {
		set_new_kanban(false);
		visit_board();
		// Classic markup renders; the new engine's container is gone.
		cy.get(".kanban-column", { timeout: 15000 }).should("have.length.at.least", 3);
		cy.get(".new-kanban-container").should("not.exist");
	});

	after(() => {
		// Leave the setting off (idempotent) so other specs get the classic board.
		set_new_kanban(false);
		cy.call("logout");
	});
});
