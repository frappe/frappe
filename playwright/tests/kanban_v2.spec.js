import { test, expect } from "../support";

// same board as the classic suite; its use_kanban_v2 flag picks the UI
const TODO_KANBAN_URL = "/desk/todo/view/kanban/ToDo Kanban";

const is_post_to = (method) => (res) =>
	res.request().method() === "POST" && res.url().includes(`/api/method/${method}`);

const set_kanban_v2 = (admin, enabled) =>
	admin.set_value("Kanban Board", "ToDo Kanban", { use_kanban_v2: enabled ? 1 : 0 });

const column_cards = (page, column) => page.locator(`.kn-column[data-col="${column}"] .kn-card`);

// a full page load, so the use_kanban_v2 flag is read again
async function visit_board(page) {
	const board_data = page.waitForResponse(
		is_post_to("frappe.desk.doctype.kanban_board.kanban_board.get_kanban_board_data")
	);
	await page.goto(TODO_KANBAN_URL);
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
