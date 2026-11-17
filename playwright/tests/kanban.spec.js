import { test, expect } from "../support";

const TODO_KANBAN_URL = "/app/todo/view/kanban/ToDo Kanban";
const KANBAN_BOARD = "frappe.desk.doctype.kanban_board.kanban_board";
const NOT_SYSTEM_MANAGER = "nosysmanager@example.com";

const is_post_to = (method) => (res) =>
	res.request().method() === "POST" && res.url().includes(`/api/method/${method}`);

const open_cards = (page) =>
	page.locator('.kanban-column[data-column-value="Open"] .kanban-cards');

const settled = (page) => page.waitForFunction(() => frappe.request.ajax_count === 0);

async function visit_todo_kanban(page) {
	await page.goto(TODO_KANBAN_URL);
	await expect(page.locator(".kanban-column").nth(1)).toBeAttached();
	// a freshly rendered board saves its card order
	await settled(page);
}

async function open_kanban_settings(page) {
	await page.locator(".page-actions .menu-btn-group > .btn").click();
	await page
		.locator(".page-actions .menu-btn-group .dropdown-menu li", { hasText: "Kanban Settings" })
		.click();
	await expect(page.locator(".modal:visible .add-new-fields")).toBeVisible();
}

async function save_kanban_settings(page, desk) {
	const saved = page.waitForResponse(is_post_to(`${KANBAN_BOARD}.save_settings`));
	await desk
		.get_open_dialog()
		.locator(".frappe-control .label-area", { hasText: "Show Labels" })
		.click();
	await desk.click_modal_primary_button("Save");
	await saved;
}

test.describe("Kanban Board", () => {
	test.describe.configure({ mode: "serial" });

	test.beforeAll(async ({ admin }) => {
		const boards = await admin.get_list(
			"Kanban Board",
			["name"],
			[["reference_doctype", "=", "ToDo"]]
		);
		for (const board of boards.data) {
			await admin.remove_doc("Kanban Board", board.name);
		}
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("User", NOT_SYSTEM_MANAGER, true);
	});

	test("Create ToDo Kanban", async ({ page, desk, api }) => {
		await api.call("frappe.model.utils.user_settings.save", {
			doctype: "ToDo",
			user_settings: JSON.stringify({ Kanban: null }),
		});
		await page.goto("/app/todo");
		await desk.ready();

		await page.locator(".page-actions .custom-btn-group button").click();
		await page
			.locator(".page-actions .custom-btn-group ul.dropdown-menu li", { hasText: "Kanban" })
			.click();

		await expect(page.locator(".modal-dialog:visible")).toBeAttached();
		await desk.fill_field("board_name", "ToDo Kanban", "Data");
		await desk.fill_field("field_name", "Status", "Select");
		await desk.click_modal_primary_button("Save");

		await expect(page.locator(".title-text:visible")).toContainText("ToDo Kanban");
	});

	test("Create ToDo from kanban", async ({ page, desk }) => {
		await visit_todo_kanban(page);

		await desk.click_primary_button("Add ToDo");

		await desk.fill_field("description", "Test Kanban ToDo", "Text Editor");
		await expect
			.poll(() => page.evaluate(() => frappe.quick_entry?.doc.description))
			.toContain("Test Kanban ToDo");

		const save_todo = page.waitForResponse(is_post_to("frappe.client.save"));
		await page.locator(".modal-footer .btn-primary:visible").last().click();
		await save_todo;
	});

	test("Add and Remove fields", async ({ page, desk }) => {
		await visit_todo_kanban(page);

		await open_kanban_settings(page);
		await page.locator(".modal:visible .add-new-fields").click();

		const field_dialog = desk.get_open_dialog();
		await expect(field_dialog.locator(".modal-title")).toContainText("Fields");
		for (const label of ["ID", "Status", "Priority"]) {
			await field_dialog
				.locator(".checkbox-options .checkbox", { hasText: label })
				.first()
				.locator('input[type="checkbox"]')
				.check();
		}
		await field_dialog.locator(".modal-footer .btn-primary").click();
		await expect(desk.get_open_dialog().locator(".modal-title")).toContainText(
			"ToDo Settings"
		);

		await save_kanban_settings(page, desk);

		const first_card = open_cards(page).locator(".kanban-card .kanban-card-doc").first();
		await expect(first_card).toContainText("ID:");
		await expect(first_card).toContainText("Status:");
		await expect(first_card).toContainText("Priority:");

		await open_kanban_settings(page);
		await desk
			.get_open_dialog()
			.locator(
				'.frappe-control[data-fieldname="fields_html"] div[data-label="ID"] .remove-field'
			)
			.click();
		await expect(
			desk
				.get_open_dialog()
				.locator('.frappe-control[data-fieldname="fields_html"] div[data-label="ID"]')
		).toHaveCount(0);

		await save_kanban_settings(page, desk);

		await expect(first_card).toBeAttached();
		await expect(first_card).not.toContainText("ID:");
	});

	test("Checks if Kanban Board edits are blocked for non-System Manager and non-owner of the Board", async ({
		page,
		desk,
		admin,
	}) => {
		await admin.call("frappe.tests.ui_test_helpers.create_test_user", {
			username: NOT_SYSTEM_MANAGER,
		});
		await admin.call("frappe.tests.ui_test_helpers.add_remove_role", {
			action: "remove",
			user: NOT_SYSTEM_MANAGER,
			role: "System Manager",
		});
		await admin.call("frappe.tests.ui_test_helpers.create_todo", {
			description: "Frappe User ToDo",
		});
		await admin.call("frappe.tests.ui_test_helpers.create_admin_kanban");

		await desk.login(NOT_SYSTEM_MANAGER);

		await page.goto("/app/todo/view/kanban/Admin Kanban");
		await expect(page.locator(".kanban .kanban-column")).toHaveCount(2);
		await page.waitForFunction(() => cur_list.board_perms);
		await settled(page);

		await expect(
			page.locator(
				".no-list-sidebar .menu-btn-group .btn-default[data-original-title='Menu']"
			)
		).toBeHidden();
		await expect(page.locator(".kanban .add-card")).toHaveCount(2);
		await expect(page.locator(".kanban .column-options")).toHaveCount(0);
	});
});
