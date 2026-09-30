context("Kanban v2 Board", () => {
	// same board as the classic suite; its use_kanban_v2 flag picks the UI
	const TODO_KANBAN_URL = "/desk/todo/view/kanban/ToDo Kanban";

	const set_kanban_v2 = (enabled) =>
		cy.set_value("Kanban Board", "ToDo Kanban", { use_kanban_v2: enabled ? 1 : 0 });

	// a full page load, so the use_kanban_v2 flag is read again
	const visit_board = () => {
		cy.intercept(
			"POST",
			"**/api/method/frappe.desk.doctype.kanban_board.kanban_board.get_kanban_board_data"
		).as("kanban-board-data");
		cy.visit(TODO_KANBAN_URL);
		cy.wait("@kanban-board-data");
	};

	const visit_kanban_v2 = () => {
		visit_board();
		cy.get(".kanban-v2-container", { timeout: 15000 }).should("exist");
		cy.get(".kn-column").should("have.length.at.least", 3);
	};

	before(() => {
		cy.login(); // Administrator, to set the Kanban Board flag
		cy.visit("/desk");
		cy.call("frappe.tests.ui_test_helpers.ensure_todo_kanban_board");
		cy.call("frappe.tests.ui_test_helpers.create_todo_records");
		set_kanban_v2(true);
	});

	it("renders the new Kanban board instead of the classic one", () => {
		visit_kanban_v2();
		cy.get(".kanban-column").should("not.exist");
		cy.get('.kn-column[data-col="Open"]').should("exist");
		cy.get('.kn-column[data-col="Closed"]').should("exist");
		cy.get(".title-text").should("contain", "ToDo Kanban");
	});

	it("shows cards with titles in the Open column", () => {
		visit_kanban_v2();
		cy.get('.kn-column[data-col="Open"] .kn-card')
			.should("have.length.at.least", 1)
			.first()
			.find(".kn-card-title")
			.should("not.be.empty");
	});

	it("creates a ToDo from the primary action", () => {
		cy.intercept({ method: "POST", url: "api/method/frappe.client.save" }).as("save-todo");
		visit_kanban_v2();

		// card titles are document names, so count cards instead of matching the description
		cy.get('.kn-column[data-col="Open"] .kn-card').then(($before) => {
			const before = $before.length;

			cy.click_listview_primary_button("Add ToDo");
			cy.fill_field("description", "New Kanban Test ToDo", "Text Editor").wait(300);
			cy.get(".modal-footer .btn-modal-primary").last().click();
			cy.wait("@save-todo");

			// the primary action is a plain frappe.new_doc, so reload to see the card
			visit_kanban_v2();
			cy.get('.kn-column[data-col="Open"] .kn-card', { timeout: 15000 }).should(
				"have.length",
				before + 1
			);
		});
	});

	it("opens a pre-filled create dialog when adding a card to a column", () => {
		visit_kanban_v2();

		cy.get('.kn-column[data-col="Closed"]').find(".kn-add-card").click({ force: true });

		cy.get_open_dialog().should("be.visible");
		cy.window().its("frappe.quick_entry").should("exist");
		cy.window().then((win) => {
			expect(win.frappe.quick_entry.doc.status).to.equal("Closed");
		});
		cy.hide_dialog();
	});

	it("moves a card to another column and saves it", () => {
		cy.intercept("POST", "**/api/method/frappe.client.set_value").as("set-value");

		visit_kanban_v2();
		cy.get('.kn-column[data-col="Open"] .kn-card').should("have.length.at.least", 1);

		cy.get('.kn-column[data-col="Open"] .kn-card')
			.first()
			.invoke("attr", "data-name")
			.then((name) => {
				// Cypress can't reliably simulate native HTML5 drag and drop, so call the move directly
				cy.window().then((win) =>
					win.cur_list._kanban.board.engine.applyMove(name, "Open", "Closed", 0)
				);
				cy.wait("@set-value").its("response.statusCode").should("eq", 200);

				visit_kanban_v2();
				cy.get(`.kn-column[data-col="Closed"] .kn-card[data-name="${name}"]`).should(
					"exist"
				);
				cy.get(`.kn-column[data-col="Open"] .kn-card[data-name="${name}"]`).should(
					"not.exist"
				);
			});
	});

	it("falls back to the classic Kanban board when the setting is disabled", () => {
		set_kanban_v2(false);
		visit_board();
		cy.get(".kanban-column", { timeout: 15000 }).should("have.length.at.least", 3);
		cy.get(".kanban-v2-container").should("not.exist");
	});

	after(() => {
		// other specs expect the classic board
		set_kanban_v2(false);
		cy.call("logout");
	});
});
