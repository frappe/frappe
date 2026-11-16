import { test, expect } from "../support";

// same board as the classic suite; its use_kanban_v2 flag picks the UI
const TODO_KANBAN_URL = "/desk/todo/view/kanban/ToDo Kanban";

const is_post_to = (method) => (res) =>
	res.request().method() === "POST" && res.url().includes(`/api/method/${method}`);

const set_kanban_v2 = (admin, enabled) =>
	admin.set_value("Kanban Board", "ToDo Kanban", { use_kanban_v2: enabled ? 1 : 0 });

const column_cards = (page, column) => page.locator(`.kn-column[data-col="${column}"] .kn-card`);
const card_names = (page, column) =>
	column_cards(page, column).evaluateAll((cards) => cards.map((card) => card.dataset.name));
const board_filters = (page) =>
	page.evaluate(() => cur_list._kanban.get_effective_filters().map((f) => f.slice(1, 4)));
// the List view's page stays in the DOM, with its own filter button
const board_filter_count = (page) =>
	page.locator(
		'[data-page-route="List/ToDo/Kanban/ToDo Kanban"] .filter-selector .filter-label'
	);
const priority_box = (page) =>
	page.locator('.kanban-v2-quick-filters select[data-fieldname="priority"]');
const wait_for_board_data = (page) =>
	page.waitForResponse(
		is_post_to("frappe.desk.doctype.kanban_board.kanban_board.get_kanban_board_data")
	);

// a full page load, so the use_kanban_v2 flag is read again
async function visit_board(page, query = "") {
	const board_data = wait_for_board_data(page);
	await page.goto(TODO_KANBAN_URL + query);
	await board_data;
}

// in the app, so the board opens again on the page the last visit left behind
async function reopen_board(page) {
	await page.evaluate(() => frappe.set_route("List", "ToDo"));
	await expect(page.locator(".kanban-v2-container")).toBeHidden();
	const board_data = wait_for_board_data(page);
	await page.evaluate(() => frappe.set_route("List", "ToDo", "Kanban", "ToDo Kanban"));
	await board_data;
}

async function visit_kanban_v2(page) {
	await visit_board(page);
	await expect(page.locator(".kanban-v2-container")).toBeAttached();
	await expect(page.locator(".kn-column").nth(2)).toBeAttached();
}

test.describe("Kanban v2 Board", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.ensure_todo_kanban_board");
		await admin.call("frappe.tests.ui_test_helpers.create_todo_records");
		await set_kanban_v2(admin, true);
	});

	test.afterAll(async ({ admin }) => {
		// other specs expect the classic board
		await set_kanban_v2(admin, false);
	});

	test("renders the new Kanban board instead of the classic one", async ({ page }) => {
		await visit_kanban_v2(page);
		await expect(page.locator(".kanban-column")).toHaveCount(0);
		await expect(page.locator('.kn-column[data-col="Open"]')).toBeAttached();
		await expect(page.locator('.kn-column[data-col="Closed"]')).toBeAttached();
		await expect(page.locator(".navbar-breadcrumbs:visible li:last-child")).toContainText(
			"ToDo Kanban"
		);
		await expect(column_cards(page, "Open").first().locator(".kn-card-title")).not.toBeEmpty();
	});

	test("creates a ToDo from the primary action", async ({ page, desk }) => {
		await visit_kanban_v2(page);

		// card titles are document names, so count cards instead of matching the description
		const open_cards = column_cards(page, "Open");
		await expect(open_cards.first()).toBeAttached();
		const before = await open_cards.count();

		await desk.click_primary_button("Add ToDo");
		await desk.fill_field("description", "New Kanban Test ToDo", "Text Editor");
		await expect
			.poll(() => page.evaluate(() => frappe.quick_entry?.doc.description))
			.toContain("New Kanban Test ToDo");
		const save_todo = page.waitForResponse(is_post_to("frappe.client.save"));
		await page.locator(".modal-footer .btn-modal-primary:visible").last().click();
		await save_todo;

		// the primary action is a plain frappe.new_doc, so reload to see the card
		await visit_kanban_v2(page);
		await expect(open_cards).toHaveCount(before + 1);
	});

	test("opens a pre-filled create dialog when adding a card to a column", async ({
		page,
		desk,
	}) => {
		await visit_kanban_v2(page);

		await page.locator('.kn-column[data-col="Closed"] .kn-add-card').click();

		await expect(desk.get_open_dialog()).toBeVisible();
		await expect
			.poll(() => page.evaluate(() => frappe.quick_entry?.doc.status))
			.toBe("Closed");
		await desk.hide_dialog();
	});

	test("moves a card to another column and saves it", async ({ page }) => {
		await visit_kanban_v2(page);
		const first_open_card = column_cards(page, "Open").first();
		await expect(first_open_card).toBeAttached();

		const name = await first_open_card.getAttribute("data-name");
		const set_value = page.waitForResponse(is_post_to("frappe.client.set_value"));
		// native HTML5 drag and drop can't be simulated reliably, so call the move directly
		await page.evaluate(
			(name) => cur_list._kanban.board.engine.applyMove(name, "Open", "Closed", 0),
			name
		);
		expect((await set_value).status()).toBe(200);

		await visit_kanban_v2(page);
		await expect(
			page.locator(`.kn-column[data-col="Closed"] .kn-card[data-name="${name}"]`)
		).toBeAttached();
		await expect(
			page.locator(`.kn-column[data-col="Open"] .kn-card[data-name="${name}"]`)
		).toHaveCount(0);
	});

	test("leaves the doctype room when the board closes", async ({ page }) => {
		await visit_kanban_v2(page);
		const room_users = () =>
			page.evaluate(() => frappe.realtime.subscribed_doctypes.get("ToDo") || 0);
		const on_board = await room_users();

		await page.evaluate(() => frappe.set_route("List", "User"));
		await expect.poll(room_users).toBe(on_board - 1);
	});

	test("applies a route filter for that visit only", async ({ page, admin }) => {
		const { data: open_todos } = await admin.get_list(
			"ToDo",
			["name"],
			[["status", "=", "Open"]]
		);
		expect(open_todos.length).toBeGreaterThan(1);
		const high = open_todos[0].name;
		await admin.set_value("ToDo", high, { priority: "High" });
		try {
			await visit_board(page, "?priority=High");
			await expect(column_cards(page, "Open")).toHaveCount(1);
			await expect(column_cards(page, "Open").first()).toHaveAttribute("data-name", high);
			await expect(priority_box(page)).toHaveValue("High");
			await expect(board_filter_count(page)).toHaveText("1");

			await reopen_board(page);
			await expect(priority_box(page)).toHaveValue("");
			await expect(board_filter_count(page)).toBeHidden();
			expect(await board_filters(page)).toEqual([]);
			await expect(column_cards(page, "Open")).toHaveCount(open_todos.length);
		} finally {
			await admin.set_value("ToDo", high, { priority: "Medium" });
		}
	});

	test("keeps a typed quick filter when the board opens again", async ({ page, admin }) => {
		const { data: open_todos } = await admin.get_list(
			"ToDo",
			["name"],
			[["status", "=", "Open"]]
		);
		expect(open_todos.length).toBeGreaterThan(1);
		const high = open_todos[0].name;
		await admin.set_value("ToDo", high, { priority: "High" });
		try {
			await visit_kanban_v2(page);
			const filtered = wait_for_board_data(page);
			await priority_box(page).selectOption("High");
			await filtered;
			await expect(column_cards(page, "Open")).toHaveCount(1);

			await reopen_board(page);
			await expect(priority_box(page)).toHaveValue("High");
			await expect(column_cards(page, "Open")).toHaveCount(1);
			await expect(column_cards(page, "Open").first()).toHaveAttribute("data-name", high);
		} finally {
			await admin.set_value("ToDo", high, { priority: "Medium" });
		}
	});

	test("orders the cards with the sort selector", async ({ page }) => {
		await visit_kanban_v2(page);
		await expect(column_cards(page, "Open").nth(1)).toBeAttached();
		const before = await card_names(page, "Open");
		const order = page.locator(".kanban-v2-filter-section .sort-selector .btn-order");

		const reversed = wait_for_board_data(page);
		await order.click();
		await reversed;
		await expect.poll(() => card_names(page, "Open")).toEqual([...before].reverse());

		// the sort is remembered per board, so put it back
		const restored = wait_for_board_data(page);
		await order.click();
		await restored;
		await expect.poll(() => card_names(page, "Open")).toEqual(before);
	});

	test("keeps the card in its column when onBeforeCardMove returns false", async ({ page }) => {
		await visit_kanban_v2(page);
		await page.evaluate(() => {
			window.before_moves = [];
			frappe.kanban_v2.settings["ToDo"] = {
				callbacks: {
					onBeforeCardMove(move, board_page) {
						window.before_moves.push({
							name: move.cardId,
							title: move.title,
							doc_name: move.doc?.name,
							board_name: move.board_name,
							is_page: board_page === cur_list._kanban,
						});
						return false;
					},
				},
			};
		});
		// settings are read when the board loads
		await reopen_board(page);

		const name = await column_cards(page, "Open").first().getAttribute("data-name");
		let saved = false;
		page.on("request", (request) => {
			if (request.url().includes("/api/method/frappe.client.set_value")) saved = true;
		});
		await page.evaluate(
			(name) => cur_list._kanban.board.engine.applyMove(name, "Open", "Closed", 0),
			name
		);

		expect(saved).toBe(false);
		await expect(
			page.locator(`.kn-column[data-col="Open"] .kn-card[data-name="${name}"]`)
		).toBeAttached();
		const moves = await page.evaluate(() => window.before_moves);
		expect(moves).toHaveLength(1);
		expect(moves[0]).toMatchObject({
			name,
			doc_name: name,
			board_name: "ToDo Kanban",
			is_page: true,
		});
		expect(moves[0].title).toBeTruthy();
	});

	test("shows one message when the server refuses a move", async ({ page }) => {
		await visit_kanban_v2(page);
		await page.route("**/api/method/frappe.client.set_value", (route) =>
			route.fulfill({
				status: 403,
				json: { exc_type: "PermissionError", _error_message: "Not allowed to move" },
			})
		);

		const name = await column_cards(page, "Open").first().getAttribute("data-name");
		const refused = page.waitForResponse(is_post_to("frappe.client.set_value"));
		await page.evaluate(
			(name) => cur_list._kanban.board.engine.applyMove(name, "Open", "Closed", 0),
			name
		);
		expect((await refused).status()).toBe(403);

		await expect(page.locator(".msgprint")).toContainText("Not allowed to move");
		await expect(
			page.locator(`.kn-column[data-col="Open"] .kn-card[data-name="${name}"]`)
		).toBeAttached();
		// applyMove resolves after onMoveError, so a second message would be up by now
		await expect(page.locator(".es-toast", { hasText: "Could not move" })).toHaveCount(0);
	});

	test("folds the sidebar while the board shows and unfolds it after", async ({ page }) => {
		await visit_kanban_v2(page);
		await expect(page.locator("body")).toHaveClass(/(^|\s)sidebar-collapsed(\s|$)/);
		// the viewer's own choice is an open sidebar
		await page.evaluate(() => localStorage.setItem("desk-sidebar-collapsed", "0"));

		await page.evaluate(() => frappe.set_route("List", "ToDo"));
		await expect(page.locator(".kanban-v2-container")).toBeHidden();
		await expect(page.locator("body")).not.toHaveClass(/(^|\s)sidebar-collapsed(\s|$)/);
	});

	test("falls back to the classic Kanban board when the setting is disabled", async ({
		page,
		admin,
	}) => {
		await set_kanban_v2(admin, false);
		// the classic board saves its column order to the board on load
		const order_saved = page.waitForResponse(
			is_post_to("frappe.desk.doctype.kanban_board.kanban_board.update_order")
		);
		await visit_board(page);
		await expect(page.locator(".kanban-column").nth(2)).toBeAttached();
		await expect(page.locator(".kanban-v2-container")).toHaveCount(0);
		// let that save land before afterAll writes to the same board
		await order_saved;
	});
});
