import { test, expect, use_shared_page, TEST_USER } from "../support";

test.describe("Workspace Blocks", () => {
	const shared = use_shared_page();
	const save_button = '.standard-actions .btn-primary[data-label="Save"]';

	test("Create Test Page", async () => {
		const { page, desk, api } = shared;
		const sidebar_item = page.locator('.sidebar-item-container[item-name="Test Block Page"]');

		await api.remove_doc("Workspace", `Test Block Page-${TEST_USER}`, true);

		await page.goto("/app/website");
		await expect(page.locator(".codex-editor__redactor .ce-block").first()).toBeAttached();
		await page.locator(".btn-new-workspace").click();
		await desk.fill_field("title", "Test Block Page", "Data");
		await desk.get_open_dialog().locator(".modal-header").click();
		const new_page = page.waitForResponse(
			(res) =>
				res.request().method() === "POST" &&
				res.url().includes("api/method/frappe.desk.doctype.workspace.workspace.new_page")
		);
		await desk.get_open_dialog().locator(".btn-primary").click();
		await new_page;

		await expect(sidebar_item).toHaveAttribute("item-public", "0");
		await page.locator(save_button).click();
		await expect(sidebar_item).toHaveAttribute("item-public", "0");
	});

	test("Number Card Block", async () => {
		const { page, desk, api } = shared;
		const number_card = page.locator(".ce-block .number-widget-box").first();
		const widget_title = number_card.locator(".widget-title");

		await api.create_records([
			{
				doctype: "Number Card",
				label: "Test Number Card",
				document_type: "ToDo",
				color: "#f74343",
			},
		]);

		await expect(page.locator(".codex-editor__redactor .ce-block").first()).toBeAttached();
		await page.locator(".btn-edit-workspace").click();

		await page.locator(".ce-block").first().click();
		await page.keyboard.press("Enter");
		await page
			.locator(".block-list-container .block-list-item")
			.getByText("Number Card")
			.first()
			.click();

		await desk.fill_field("number_card_name", "Test Number Card", "Link");
		await desk.click_modal_primary_button("Add");
		await expect(widget_title).toContainText("Test Number Card");
		await page.locator(save_button).click();
		await expect(widget_title).toContainText("Test Number Card");

		await page.locator(".btn-edit-workspace").click();
		await number_card.hover();
		await number_card.locator(".widget-control .edit-button").click();
		await desk.get_field("label", "Data").evaluate((input) => {
			input.value = "ToDo Count";
		});
		await desk.click_modal_primary_button("Save");
		await expect(widget_title).toContainText("ToDo Count");
		await page.locator(save_button).click();
		await expect(widget_title).toContainText("ToDo Count");
	});
});
