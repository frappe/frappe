import { test, expect, use_shared_page } from "../support";

const TITLES = ["Test Child Page", "Duplicate Page", "Test Private Page", "Test Private Page 1"];

test.describe("Workspace 2.0", () => {
	const shared = use_shared_page();
	const save_button = '.standard-actions .btn-primary[data-label="Save"]';
	const discard_button = '.standard-actions .btn-secondary[data-label="Discard"]';

	const sidebar_item = (name) =>
		shared.page.locator(`.sidebar-item-container[item-name="${name}"]`);

	const workspace_call = (method) =>
		shared.page.waitForResponse(
			(res) =>
				res.request().method() === "POST" &&
				res.url().includes(`api/method/frappe.desk.doctype.workspace.workspace.${method}`)
		);

	const editor_ready = () =>
		expect(shared.page.locator(".codex-editor__redactor .ce-block").first()).toBeAttached();

	async function edit_workspace() {
		await editor_ready();
		await shared.page.locator(".btn-edit-workspace").click();
		await expect(
			shared.page.locator(".standard-sidebar-section.show-control").first()
		).toBeAttached();
	}

	async function open_item_menu(name, action) {
		const item = sidebar_item(name);
		await item.locator(".sidebar-item-control .setting-btn").first().click();
		await item.locator(`.dropdown-list .dropdown-item[title="${action}"]`).first().click();
	}

	async function drag_item(name) {
		const handle = sidebar_item(name).locator(".drag-handle").first();
		await sidebar_item(name).locator(".standard-sidebar-item").first().hover();
		const box = await handle.boundingBox();
		const x = box.x + box.width / 2;
		const y = box.y + box.height / 2;
		await shared.page.mouse.move(x, y);
		await shared.page.mouse.down();
		await shared.page.mouse.move(x, y + 100, { steps: 10 });
		await shared.page.mouse.up();
	}

	test.beforeAll(async ({ admin }) => {
		const { data } = await admin.get_list(
			"Workspace",
			["name", "title"],
			[["title", "in", TITLES]]
		);
		data.sort((a, b) => TITLES.indexOf(a.title) - TITLES.indexOf(b.title));
		for (const { name } of data) {
			await admin.remove_doc("Workspace", name, true);
		}
	});

	test("Navigate to page from sidebar", async () => {
		const { page } = shared;
		await page.goto("/app/build");
		await editor_ready();
		await sidebar_item("Website").first().click();
		await expect(page).toHaveURL((url) => url.pathname === "/app/website");
	});

	test("Create Private Page", async () => {
		const { page, desk } = shared;
		const new_page = workspace_call("new_page");

		await editor_ready();
		await page.locator(".btn-new-workspace").click();
		await desk.fill_field("title", "Test Private Page", "Data");
		await desk.get_open_dialog().locator(".modal-header").click();
		await desk.get_open_dialog().locator(".btn-primary").click();

		await new_page;
		await expect(sidebar_item("Test Private Page")).toHaveAttribute("item-public", "0");
		const saved = workspace_call("save_page");
		await page.locator(save_button).click();
		await saved;
		await expect(sidebar_item("Test Private Page")).toHaveAttribute("item-public", "0");
	});

	test("Create Child Page", async () => {
		const { page, desk } = shared;
		const new_page = workspace_call("new_page");

		await editor_ready();
		await page.locator(".btn-new-workspace").click();
		await desk.fill_field("title", "Test Child Page", "Data");
		await desk.fill_field("parent", "Test Private Page", "Select");
		await desk.get_open_dialog().locator(".modal-header").click();
		await desk.get_open_dialog().locator(".btn-primary").click();

		await new_page;
		await expect(sidebar_item("Test Child Page")).toHaveAttribute("item-public", "0");
		const saved = workspace_call("save_page");
		await page.locator(save_button).click();
		await saved;
		await expect(sidebar_item("Test Child Page")).toHaveAttribute("item-public", "0");
	});

	test("Duplicate Page", async () => {
		const { desk } = shared;
		const page_duplicated = workspace_call("duplicate_page");

		await edit_workspace();
		const item = sidebar_item("Test Private Page");
		await item.locator(".standard-sidebar-item").first().click();
		await item.locator(".dropdown-btn").first().click();
		await item
			.locator(".dropdown-list .dropdown-item", { hasText: "Duplicate" })
			.first()
			.click();

		await desk.fill_field("title", "Duplicate Page", "Data");
		await desk.click_modal_primary_button("Duplicate");

		await page_duplicated;
	});

	test("Drag Sidebar Item", async () => {
		const page_sorted = workspace_call("sort_pages");

		await drag_item("Duplicate Page");
		await drag_item("Build");

		await page_sorted;
	});

	test("Edit Page Detail", async () => {
		const { page, desk } = shared;
		const page_updated = workspace_call("update_page");

		const item = sidebar_item("Test Private Page");
		await item.locator(".standard-sidebar-item").first().click();
		await item.locator(".dropdown-btn").first().click();
		await item.locator(".dropdown-list .dropdown-item", { hasText: "Edit" }).first().click();

		const dialog = desk.get_open_dialog();
		await desk.type(dialog.locator('[data-fieldname="title"] input'), " 1");
		await dialog.locator('input[data-fieldname="is_public"]').check();
		await desk.click_modal_primary_button("Update");

		await expect(
			page
				.locator(".standard-sidebar-section")
				.first()
				.locator('.sidebar-item-container[item-name="Test Private Page"]')
		).toHaveCount(0);
		await expect(
			page
				.locator(".standard-sidebar-section")
				.last()
				.locator('.sidebar-item-container[item-name="Test Private Page 1"]')
		).toBeAttached();

		await page_updated;
	});

	test("Add New Block", async () => {
		const { page } = shared;
		const last_block = page.locator(".ce-block").last();
		const block_list = page.locator(".block-list-container .block-list-item");

		await sidebar_item("Duplicate Page").locator(".standard-sidebar-item").first().click();

		await page.locator(".ce-block").click();
		await page.keyboard.press("Enter");
		await block_list.getByText("Heading").first().click();
		await page.locator(":focus").pressSequentially("Header");
		await expect(last_block.locator(".ce-header")).toBeAttached();

		await last_block.click();
		await page.keyboard.press("Enter");
		await block_list.getByText("Text").first().click();
		await page.locator(":focus").pressSequentially("Paragraph text");
		await expect(last_block.locator(".ce-paragraph")).toBeAttached();
	});

	test("Delete A Block", async () => {
		const { page } = shared;

		await page.locator(":focus").click();
		await page.locator(".paragraph-control .setting-btn").click();
		await page
			.locator(".paragraph-control .dropdown-item")
			.getByText("Delete")
			.first()
			.click();
		await expect(page.locator(".ce-block").last().locator(".ce-paragraph")).toHaveCount(0);
	});

	test("Shrink and Expand A Block", async () => {
		const { page } = shared;
		const last_block = page.locator(".ce-block").last();
		const resize = async (action, expected_class) => {
			await last_block.locator(".dropdown-item").getByText(action).first().click();
			await expect(last_block).toHaveClass(new RegExp(`(^|\\s)${expected_class}(\\s|$)`));
		};

		await page.locator(":focus").click();
		await last_block.locator(".setting-btn").click();
		await resize("Shrink", "col-xs-11");
		await resize("Shrink", "col-xs-10");
		await resize("Shrink", "col-xs-9");
		await resize("Expand", "col-xs-10");
		await resize("Expand", "col-xs-11");
		await resize("Expand", "col-xs-12");
		await page.locator(save_button).click();
	});

	test("Hide/Unhide Workspaces", async () => {
		const { page } = shared;
		const hide_page = workspace_call("hide_page");

		await edit_workspace();
		await open_item_menu("Duplicate Page", "Hide Workspace");
		await hide_page;
		await page.locator(discard_button).click();
		await expect(sidebar_item("Duplicate Page")).toBeHidden();

		const unhide_page = workspace_call("unhide_page");
		await edit_workspace();
		await sidebar_item("Duplicate Page").locator('[title="Unhide Workspace"]').click();
		await unhide_page;
		await page.locator(discard_button).click();
		await expect(sidebar_item("Duplicate Page")).toBeVisible();
	});

	test("Delete Duplicate Page", async () => {
		const { page } = shared;
		const page_deleted = workspace_call("delete_page");

		await edit_workspace();
		await open_item_menu("Duplicate Page", "Delete Workspace");
		await page
			.locator(".modal-footer > .standard-actions > .btn-modal-primary:visible")
			.first()
			.click();
		await expect(sidebar_item("Duplicate Page")).toHaveCount(0);

		await page_deleted;
	});
});
