import { test, expect, use_shared_page, TEST_USER } from "../support";

test.describe("Workspace 2.0", () => {
	const shared = use_shared_page();
	const save_button = '.standard-actions .primary-action[data-label="Save"]';

	test.beforeAll(async ({ admin }) => {
		await admin.remove_doc("Workspace", `Test Private Page-${TEST_USER}`, true);
	});

	test.fixme("Navigate to page from sidebar", async () => {
		const { page } = shared;
		await page.goto("/desk/build");
		await expect(page.locator(".codex-editor__redactor .ce-block").first()).toBeAttached();
		await page.locator('.sidebar-item-container[item-name="Page"]').first().click();
		await expect(page).toHaveURL((url) => url.pathname === "/desk/page");
	});

	test.fixme("Create Private Page", async () => {
		const { page, desk } = shared;
		const sidebar_item = page.locator(
			'.sidebar-item-container[item-name="Test Private Page"]'
		);

		await page.goto("/desk/website");
		await expect(page.locator(".codex-editor__redactor .ce-block").first()).toBeAttached();
		await page.locator(".btn-new-workspace").click();
		await desk.fill_field("title", "Test Private Page", "Data");
		await desk.fill_field("type", "Workspace", "Select");

		await desk.get_open_dialog().locator(".modal-header").click();
		const new_page = page.waitForResponse(
			(res) =>
				res.request().method() === "POST" &&
				res.url().includes("api/method/frappe.desk.doctype.workspace.workspace.new_page")
		);
		await desk.get_open_dialog().locator(".btn-modal-primary").click();
		await new_page;

		await expect(sidebar_item).toBeAttached();
		await page.locator(save_button).click();
		await expect(sidebar_item).toBeAttached();
	});

	test.fixme("Add New Block", async () => {
		const { page } = shared;
		const last_block = page.locator(".ce-block").last();
		const block_list = page.locator(".block-list-container .block-list-item");

		await page.locator(".btn-edit-workspace").click();

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

	test.fixme("Delete A Block", async () => {
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

	test.fixme("Shrink and Expand A Block", async () => {
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
});
