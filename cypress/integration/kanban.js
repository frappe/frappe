context("Kanban Board", () => {
	const TODO_KANBAN_URL = "/desk/todo/view/kanban/ToDo Kanban";

	const visit_todo_kanban = () => {
		cy.intercept(
			"POST",
			"**/api/method/frappe.desk.doctype.kanban_board.kanban_board.get_kanban_board_data"
		).as("kanban-board-data");
		cy.visit(TODO_KANBAN_URL);
		cy.wait("@kanban-board-data");
		cy.get(".kanban-column").should("have.length.at.least", 2);
	};

	const scroll_open_column_to_bottom = () => {
		cy.get("@open-cards").then(($el) => {
			const el = $el[0];
			expect(el.scrollHeight).to.be.greaterThan(el.clientHeight);
			el.scrollTop = el.scrollHeight;
			el.dispatchEvent(new Event("scroll", { bubbles: true }));
		});
	};

	const wait_for_column_page_prefetch = () => {
		scroll_open_column_to_bottom();
		cy.wait("@get-kanban-column-page", { timeout: 15000 });
	};

	before(() => {
		cy.login("frappe@example.com");
		cy.visit("/desk");
		cy.call("frappe.tests.ui_test_helpers.ensure_todo_kanban_board");
	});

	it("Create ToDo Kanban", () => {
		cy.call("frappe.client.get_value", {
			doctype: "Kanban Board",
			filters: { name: "ToDo Kanban" },
			fieldname: "name",
		}).then((r) => {
			if (r.message?.name) {
				cy.visit(TODO_KANBAN_URL);
				cy.get(".title-text").should("contain", "ToDo Kanban");
				return;
			}

			cy.visit("/desk/todo");
			// the Kanban row hosts the boards submenu (it doesn't act on
			// click) — creation lives in the submenu's Create Board row
			cy.get(".page-actions .custom-btn-group button").click();
			cy.contains(".es-menu__item", "Kanban View").trigger("pointerenter");
			cy.contains(".es-menu__item", "Create Board").click();

			cy.get(".modal-dialog:visible").should("exist");
			cy.fill_field("board_name", "ToDo Kanban", "Data");
			cy.fill_field("field_name", "Status", "Select");
			cy.click_modal_primary_button("Save");

			cy.get(".title-text").should("contain", "ToDo Kanban");
		});
	});

	it("Open a board from the view switcher on list view", () => {
		cy.visit("/desk/todo");
		cy.get(".page-actions .custom-btn-group button").click();
		// boards load async at hover — the row appears once the fetch lands
		cy.contains(".es-menu__item", "Kanban View").trigger("pointerenter");
		cy.contains(".es-menu__item", "ToDo Kanban").click();

		cy.get(".title-text").should("contain", "ToDo Kanban");
		cy.window()
			.its("cur_list")
			.then((list) => {
				expect(list.view_name).to.equal("Kanban");
			});
	});

	it("Create ToDo from kanban", () => {
		cy.intercept({
			method: "POST",
			url: "api/method/frappe.client.save",
		}).as("save-todo");

		cy.click_listview_primary_button("Add ToDo");

		cy.fill_field("description", "Test Kanban ToDo", "Text Editor").wait(300);
		cy.get(".modal-footer .btn-modal-primary").last().click();

		cy.wait("@save-todo");
	});

	const save_kanban_settings = () => {
		cy.window().then((win) => {
			const settings_dialog = win.frappe.ui.open_dialogs.find((dialog) =>
				`${dialog.title}`.includes("Settings")
			);
			const settings = { ...settings_dialog.get_values(), show_labels: 1 };
			settings_dialog.set_value("show_labels", 1);

			return win.frappe.call({
				method: "frappe.desk.doctype.kanban_board.kanban_board.save_settings",
				args: {
					board_name: win.cur_list.board.name,
					settings,
				},
				callback: (r) => {
					win.cur_list.board = r.message;
					win.cur_list.render();
				},
			});
		});
	};
	const open_kanban_settings = () => {
		cy.window()
			.its("cur_list")
			.then((cur_list) => {
				cur_list.show_kanban_settings();
			});
		cy.get(".add-new-fields", { timeout: 10000 }).should("exist");
	};

	it("Add and Remove fields", () => {
		visit_todo_kanban();

		cy.intercept(
			"POST",
			"**/api/method/frappe.desk.doctype.kanban_board.kanban_board.save_settings"
		).as("save-kanban");

		open_kanban_settings();
		cy.get(".add-new-fields").click();

		cy.get_open_dialog().as("field-dialog");
		cy.get("@field-dialog")
			.contains(".checkbox", "ID")
			.find('input[type="checkbox"]')
			.check({ force: true });
		cy.get("@field-dialog")
			.contains(".checkbox", "Status")
			.find('input[type="checkbox"]')
			.check({ force: true });
		cy.get("@field-dialog")
			.contains(".checkbox", "Priority")
			.find('input[type="checkbox"]')
			.check({ force: true });
		cy.get("@field-dialog").find(".btn-modal-primary").click({ force: true });
		cy.window().then((win) => {
			win.frappe.ui.open_dialogs
				.filter((dialog) => dialog.title && `${dialog.title}`.includes("Fields"))
				.forEach((dialog) => dialog.hide());
		});
		save_kanban_settings();
		cy.wait("@save-kanban", { timeout: 15000 });

		cy.get('.kanban-column[data-column-value="Open"] .kanban-cards').as("open-cards");
		cy.get("@open-cards")
			.find(".kanban-card .kanban-card-doc")
			.first()
			.should("contain", "ID:");
		cy.get("@open-cards")
			.find(".kanban-card .kanban-card-doc")
			.first()
			.should("contain", "Status:");
		cy.get("@open-cards")
			.find(".kanban-card .kanban-card-doc")
			.first()
			.should("contain", "Priority:");

		cy.call("frappe.client.get", { doctype: "Kanban Board", name: "ToDo Kanban" }).then(
			(r) => {
				const fields = JSON.parse(r.message.fields || "[]").filter(
					(field) => field !== "name"
				);
				cy.call("frappe.desk.doctype.kanban_board.kanban_board.save_settings", {
					board_name: "ToDo Kanban",
					settings: { fields, show_labels: 1 },
				});
			}
		);

		visit_todo_kanban();
		cy.get('.kanban-column[data-column-value="Open"] .kanban-cards').as("open-cards");
		cy.get("@open-cards").find(".kanban-card .kanban-card-doc").should("not.contain", "ID:");
	});

	it("Shows fieldtype icons when labels are hidden", () => {
		cy.call("frappe.desk.doctype.kanban_board.kanban_board.save_settings", {
			board_name: "ToDo Kanban",
			settings: { fields: ["status", "priority"], show_labels: 0 },
		});

		visit_todo_kanban();
		cy.get('.kanban-column[data-column-value="Open"] .kanban-cards').as("open-cards");
		cy.get("@open-cards")
			.find(".kanban-card .kanban-card-doc")
			.first()
			.as("card-doc")
			.should("not.contain", "Status:")
			.and("not.contain", "Priority:");
		cy.get("@card-doc")
			.find(".kanban-doc-icon")
			.should("have.length.at.least", 1)
			.first()
			.should("have.attr", "title")
			.and("not.be.empty");
		cy.get("@card-doc")
			.find(".kanban-doc-icon")
			.first()
			.should("have.attr", "title", "Status");
	});

	const test_column_page_prefetch = () => {
		cy.call("frappe.tests.ui_test_helpers.create_multiple_todo_records");
		cy.intercept(
			"POST",
			"**/api/method/frappe.desk.doctype.kanban_board.kanban_board.get_kanban_column_page"
		).as("get-kanban-column-page");

		visit_todo_kanban();
		cy.get('.kanban-column[data-column-value="Open"] .kanban-cards').as("open-cards");
		cy.get("@open-cards").find(".kanban-card-wrapper").should("have.length.at.least", 1);
		cy.wait(300);

		wait_for_column_page_prefetch();
	};

	const test_drag_order_after_prefetch = () => {
		cy.call("frappe.tests.ui_test_helpers.create_multiple_todo_records");
		cy.intercept(
			"POST",
			"**/api/method/frappe.desk.doctype.kanban_board.kanban_board.get_kanban_column_page"
		).as("get-kanban-column-page");
		cy.intercept(
			"POST",
			"**/api/method/frappe.desk.doctype.kanban_board.kanban_board.update_order_for_single_card"
		).as("single-card-order");

		visit_todo_kanban();
		cy.get('.kanban-column[data-column-value="Open"] .kanban-cards').as("open-cards");
		cy.get("@open-cards").find(".kanban-card-wrapper").should("have.length.at.least", 1);
		cy.wait(300);

		wait_for_column_page_prefetch();
		cy.wait(500);

		cy.get("@open-cards")
			.find(".kanban-card-wrapper")
			.then(($cards) => {
				expect($cards.length).to.be.greaterThan(1);
				cy.wrap($cards.eq(0)).drag($cards.eq($cards.length - 1), { force: true });
			});

		cy.wait("@single-card-order", { timeout: 15000 });
	};

	it("Prefetches additional cards while scrolling a large Kanban column", () => {
		test_column_page_prefetch();
	});

	it("Saves drag-and-drop order after loading additional column pages", () => {
		test_drag_order_after_prefetch();
	});

	it.skip("Checks if Kanban Board edits are blocked for non-System Manager and non-owner of the Board", () => {
		cy.switch_to_user("Administrator");

		const not_system_manager = "nosysmanager@example.com";
		cy.call("frappe.tests.ui_test_helpers.create_test_user", {
			username: not_system_manager,
		});
		cy.remove_role(not_system_manager, "System Manager");
		cy.call("frappe.tests.ui_test_helpers.create_todo", { description: "Frappe User ToDo" });
		cy.call("frappe.tests.ui_test_helpers.create_admin_kanban");

		cy.switch_to_user(not_system_manager);

		cy.visit("/desk/todo/view/kanban/Admin Kanban");

		// Menu button should be hidden (dropdown for 'Save Filters' and 'Delete Kanban Board')
		cy.get(".no-list-sidebar .menu-btn-group .btn-default[data-original-title='Menu']").should(
			"have.length",
			0
		);
		// Kanban Columns should be visible (read-only)
		cy.get(".kanban .kanban-column").should("have.length", 2);
		// User should be able to add card (has access to ToDo)
		cy.get(".kanban .add-card").should("have.length", 2);
		// Column actions should be hidden (dropdown for 'Archive' and indicators)
		cy.get(".kanban .column-options").should("have.length", 0);

		cy.switch_to_user("Administrator");
		cy.call("frappe.client.delete", { doctype: "User", name: not_system_manager });
	});

	after(() => {
		cy.call("logout");
	});
});
