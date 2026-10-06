import { test, expect } from "../support";

// the page title is the last breadcrumb
const TITLE = ".navbar-breadcrumbs:visible li:last-child";
const TODO_KANBAN_URL = "/desk/todo/view/kanban/ToDo Kanban";
const KANBAN_BOARD = "frappe.desk.doctype.kanban_board.kanban_board";
const VIEW_SWITCHER = ".page-actions .custom-btn-group button:visible";

const is_post_to = (method) => (res) =>
	res.request().method() === "POST" && res.url().includes(`/api/method/${method}`);

const menu_item = (page, label) => page.locator(".es-menu__item", { hasText: label }).first();

const open_cards = (page) =>
	page.locator('.kanban-column[data-column-value="Open"] .kanban-cards');

async function board_loaded(page, desk) {
	await expect(page.locator(".kanban-column").nth(1)).toBeAttached();
	// a freshly rendered board saves its card order
	await desk.ready();
}

async function visit_todo_kanban(page, desk) {
	const board_data = page.waitForResponse(is_post_to(`${KANBAN_BOARD}.get_kanban_board_data`));
	await page.goto(TODO_KANBAN_URL);
	await board_data;
	await board_loaded(page, desk);
}

async function open_kanban_settings(page) {
	await page.evaluate(() => cur_list.show_kanban_settings());
	await expect(page.locator(".add-new-fields")).toBeAttached();
}

async function save_kanban_settings(page) {
	const saved = page.waitForResponse(is_post_to(`${KANBAN_BOARD}.save_settings`));
	await page.evaluate(() => {
		const settings_dialog = frappe.ui.open_dialogs.find((dialog) =>
			`${dialog.title}`.includes("Settings")
		);
		const settings = { ...settings_dialog.get_values(), show_labels: 1 };
		settings_dialog.set_value("show_labels", 1);

		frappe.call({
			method: "frappe.desk.doctype.kanban_board.kanban_board.save_settings",
			args: {
				board_name: cur_list.board.name,
				settings,
			},
			callback: (r) => {
				cur_list.board = r.message;
				cur_list.render();
			},
		});
	});
	await saved;
}

function scroll_open_column_to_bottom(page) {
	return open_cards(page).evaluate((el) => {
		if (el.scrollHeight <= el.clientHeight) {
			throw new Error("Open column is not scrollable");
		}
		el.scrollTop = el.scrollHeight;
		el.dispatchEvent(new Event("scroll", { bubbles: true }));
	});
}

// the column ignores scroll events while a render settles, so keep scrolling
// until the next page is requested
async function wait_for_column_page_prefetch(page) {
	let prefetched = false;
	const on_response = (res) => {
		if (is_post_to(`${KANBAN_BOARD}.get_kanban_column_page`)(res)) {
			prefetched = true;
		}
	};
	page.on("response", on_response);
	await expect
		.poll(
			async () => {
				if (!prefetched) {
					await scroll_open_column_to_bottom(page);
				}
				return prefetched;
			},
			{ timeout: 15000 }
		)
		.toBe(true);
	page.off("response", on_response);
}

async function open_large_todo_kanban(page, desk, api) {
	await api.call("frappe.tests.ui_test_helpers.create_multiple_todo_records");
	await visit_todo_kanban(page, desk);
	await expect(open_cards(page).locator(".kanban-card-wrapper").first()).toBeAttached();
}

test.describe("Kanban Board", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.ensure_todo_kanban_board");
	});

	test("Create ToDo Kanban", async ({ page, desk, api }) => {
		const r = await api.call("frappe.client.get_value", {
			doctype: "Kanban Board",
			filters: { name: "ToDo Kanban" },
			fieldname: "name",
		});
		if (r.message?.name) {
			await visit_todo_kanban(page, desk);
			await expect(page.locator(TITLE)).toContainText("ToDo Kanban");
			return;
		}

		await page.goto("/desk/todo");
		// the Kanban row hosts the boards submenu (it doesn't act on
		// click) — creation lives in the submenu's Create Board row
		await page.locator(VIEW_SWITCHER).click();
		await menu_item(page, "Kanban View").hover();
		await menu_item(page, "Create Board").click();

		await expect(page.locator(".modal-dialog:visible")).toBeAttached();
		await desk.fill_field("board_name", "ToDo Kanban", "Data");
		await desk.fill_field("field_name", "Status", "Select");
		await desk.click_modal_primary_button("Save");

		await expect(page.locator(TITLE)).toContainText("ToDo Kanban");
	});

	test("Open a board from the view switcher on list view", async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await page.locator(VIEW_SWITCHER).click();
		// boards load async at hover — the row appears once the fetch lands
		await menu_item(page, "Kanban View").hover();
		await menu_item(page, "ToDo Kanban").click();

		await expect(page.locator(TITLE)).toContainText("ToDo Kanban");
		await expect.poll(() => page.evaluate(() => cur_list.view_name)).toBe("Kanban");
		await board_loaded(page, desk);
	});

	test("Create ToDo from kanban", async ({ page, desk }) => {
		await visit_todo_kanban(page, desk);

		await desk.click_primary_button("Add ToDo");

		await desk.fill_field("description", "Test Kanban ToDo", "Text Editor");
		await expect
			.poll(() => page.evaluate(() => frappe.quick_entry?.doc.description))
			.toContain("Test Kanban ToDo");

		const save_todo = page.waitForResponse(is_post_to("frappe.client.save"));
		await page.locator(".modal-footer .btn-modal-primary:visible").last().click();
		await save_todo;
	});

	test("Add and Remove fields", async ({ page, desk, api }) => {
		await visit_todo_kanban(page, desk);

		await open_kanban_settings(page);
		await page.locator(".add-new-fields").click();

		const field_dialog = desk.get_open_dialog();
		for (const label of [/ID/, /Status/, /Priority/]) {
			await field_dialog
				.locator(".checkbox", { hasText: label })
				.first()
				.locator('input[type="checkbox"]')
				.check();
		}
		await field_dialog.locator(".btn-modal-primary").click();
		await page.evaluate(() => {
			frappe.ui.open_dialogs
				.filter((dialog) => dialog.title && `${dialog.title}`.includes("Fields"))
				.forEach((dialog) => dialog.hide());
		});
		await save_kanban_settings(page);

		const first_card = open_cards(page).locator(".kanban-card .kanban-card-doc").first();
		await expect(first_card).toContainText("ID:");
		await expect(first_card).toContainText("Status:");
		await expect(first_card).toContainText("Priority:");
		await board_loaded(page, desk);

		const r = await api.call("frappe.client.get", {
			doctype: "Kanban Board",
			name: "ToDo Kanban",
		});
		const fields = JSON.parse(r.message.fields || "[]").filter((field) => field !== "name");
		await api.call(`${KANBAN_BOARD}.save_settings`, {
			board_name: "ToDo Kanban",
			settings: { fields, show_labels: 1 },
		});

		await visit_todo_kanban(page, desk);
		const card_docs = open_cards(page).locator(".kanban-card .kanban-card-doc");
		await expect(card_docs.first()).toBeAttached();
		await expect(card_docs.filter({ hasText: /ID:/ })).toHaveCount(0);
	});

	test("Shows fieldtype icons when labels are hidden", async ({ page, desk, api }) => {
		await api.call(`${KANBAN_BOARD}.save_settings`, {
			board_name: "ToDo Kanban",
			settings: { fields: ["status", "priority"], show_labels: 0 },
		});

		await visit_todo_kanban(page, desk);
		const card_doc = open_cards(page).locator(".kanban-card .kanban-card-doc").first();
		await expect(card_doc).not.toContainText("Status:");
		await expect(card_doc).not.toContainText("Priority:");

		const first_icon = card_doc.locator(".kanban-doc-icon").first();
		await expect(first_icon).toHaveAttribute("title", /.+/);
		await expect(first_icon).toHaveAttribute("title", "Status");
	});

	test("Prefetches additional cards while scrolling a large Kanban column", async ({
		page,
		desk,
		api,
	}) => {
		await open_large_todo_kanban(page, desk, api);
		await wait_for_column_page_prefetch(page);
	});

	test("Saves drag-and-drop order after loading additional column pages", async ({
		page,
		desk,
		api,
	}) => {
		await open_large_todo_kanban(page, desk, api);
		await wait_for_column_page_prefetch(page);
		await desk.ready();

		// the column is virtualised: only drag between cards that are on screen
		const cards = open_cards(page).locator(".kanban-card-wrapper");
		const visible_cards = await cards.evaluateAll((cards) => {
			const column = cards[0].closest(".kanban-cards").getBoundingClientRect();
			return cards
				.map((card, index) => ({ index, rect: card.getBoundingClientRect() }))
				.filter(({ rect }) => rect.top >= column.top && rect.bottom <= column.bottom)
				.map(({ index }) => index);
		});
		expect(visible_cards.length).toBeGreaterThan(1);

		const single_card_order = page.waitForResponse(
			is_post_to(`${KANBAN_BOARD}.update_order_for_single_card`),
			{ timeout: 15000 }
		);
		await cards.nth(visible_cards[0]).dragTo(cards.nth(visible_cards.at(-1)));
		await single_card_order;
	});

	test.skip("Checks if Kanban Board edits are blocked for non-System Manager and non-owner of the Board", async ({
		page,
		desk,
		admin,
	}) => {
		const not_system_manager = "nosysmanager@example.com";
		await admin.call("frappe.tests.ui_test_helpers.create_test_user", {
			username: not_system_manager,
		});
		await admin.call("frappe.tests.ui_test_helpers.add_remove_role", {
			action: "remove",
			user: not_system_manager,
			role: "System Manager",
		});
		await admin.call("frappe.tests.ui_test_helpers.create_todo", {
			description: "Frappe User ToDo",
		});
		await admin.call("frappe.tests.ui_test_helpers.create_admin_kanban");

		await desk.login(not_system_manager);

		await page.goto("/desk/todo/view/kanban/Admin Kanban");

		await expect(
			page.locator(
				".no-list-sidebar .menu-btn-group .btn-default[data-original-title='Menu']"
			)
		).toHaveCount(0);
		await expect(page.locator(".kanban .kanban-column")).toHaveCount(2);
		await expect(page.locator(".kanban .add-card")).toHaveCount(2);
		await expect(page.locator(".kanban .column-options")).toHaveCount(0);

		await admin.call("frappe.client.delete", { doctype: "User", name: not_system_manager });
	});
});
