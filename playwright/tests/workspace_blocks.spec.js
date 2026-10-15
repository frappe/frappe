import { test, expect, use_shared_page, TEST_USER } from "../support";

test.describe("Workspace Blocks", () => {
	const shared = use_shared_page();
	const save_button = '.standard-actions .primary-action[data-label="Save"]';

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.setup_workflow");
	});

	test.fixme("Create Test Page", async () => {
		const { page, desk, api } = shared;
		const sidebar_item = page.locator('.sidebar-item-container[item-name="Test Block Page"]');

		await api.remove_doc("Workspace", `Test Block Page-${TEST_USER}`, true);

		await page.goto("/desk/website");
		await expect(page.locator(".codex-editor__redactor .ce-block").first()).toBeAttached();
		await page.locator(".btn-new-workspace").click();
		await desk.fill_field("title", "Test Block Page", "Data");
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

	test.skip("Quick List Block", async () => {
		const { page, desk, api } = shared;
		const dialog = desk.get_open_dialog();

		await api.create_records([
			{
				doctype: "ToDo",
				description: "Quick List ToDo 1",
				status: "Open",
			},
			{
				doctype: "ToDo",
				description: "Quick List ToDo 2",
				status: "Open",
			},
			{
				doctype: "ToDo",
				description: "Quick List ToDo 3",
				status: "Open",
			},
			{
				doctype: "ToDo",
				description: "Quick List ToDo 4",
				status: "Open",
			},
		]);

		await expect(page.locator(".codex-editor__redactor .ce-block").first()).toBeAttached();
		await page.locator(".btn-edit-workspace").click();

		await page.locator(".ce-block").first().click();
		await page.keyboard.press("Enter");
		await page
			.locator(".block-list-container .block-list-item")
			.getByText("Quick List")
			.first()
			.click();

		await desk.fill_field("label", "ToDo", "Data");
		const get_doctype = page.waitForResponse(
			(res) =>
				res.request().method() === "GET" &&
				res.url().includes("api/method/frappe.desk.form.load.getdoctype?")
		);
		await desk.fill_field("document_type", "ToDo", "Link");
		await get_doctype;

		await expect(dialog.locator(".filter-edit-area")).toContainText("No filters selected");
		await dialog.locator(".filter-area .add-filter").click();

		await desk.pick_filter_field("Workflow State");
		await dialog.locator(".filter-field .input-with-feedback").pressSequentially("Pending");

		await dialog.locator(".modal-header").click();
		await dialog.locator(".btn-modal-primary").click();

		await page.locator(save_button).click();

		await expect(page.locator(".codex-editor__redactor .ce-block").first()).toBeAttached();

		const quick_list = page.locator(".ce-block .quick-list-widget-box").first();

		await expect(quick_list.locator(".quick-list-item .status").first()).toContainText(
			"Pending"
		);

		const title = await quick_list
			.locator(".quick-list-item .title")
			.first()
			.getAttribute("title");
		await quick_list.locator(".quick-list-item").getByText(title).first().click();
		await expect(desk.get_field("description", "Text Editor")).toContainText(title);
		await desk.click_action_button("Approve");
		await page.goBack();

		await quick_list.hover();
		await quick_list.locator(".widget-control .filter-list").click();

		const filter_value = dialog.locator(".filter-field .input-with-feedback");
		await filter_value.focus();
		await filter_value.press("ControlOrMeta+a");
		await filter_value.pressSequentially("Approved");
		await dialog.locator(".modal-header").click();
		await dialog.locator(".btn-modal-primary").click();

		await expect(quick_list.locator(".quick-list-item .status").first()).toContainText(
			"Approved"
		);

		await quick_list.hover();
		const refresh_list = page.waitForResponse(
			(res) =>
				res.request().method() === "POST" &&
				res.url().includes("api/method/frappe.desk.reportview.get")
		);
		await quick_list.locator(".widget-control .refresh-list").click();
		await refresh_list;

		await quick_list.hover();
		await quick_list.locator(".widget-control .add-new").click();
		await expect(page).toHaveURL(/\/todo\/new-todo-1/);
		await page.goBack();

		await quick_list.locator(".widget-footer .see-all").click();
		await desk.open_list_filter();
		await expect(
			page.locator('.filter-field input[data-fieldname="workflow_state"]')
		).toHaveValue("Pending");
		await page.goBack();
	});

	test.fixme("Number Card Block", async () => {
		const { page, desk, api } = shared;
		const number_card = page.locator(".ce-block .number-widget-box").first();
		const widget_title = number_card.locator(".widget-title");

		await page.goto("/desk/private/test-block-page");
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

		const first_block = page.locator(".ce-block").first();
		await first_block.hover();
		const new_block_button = first_block.locator(".new-block-button");
		await expect(new_block_button).toBeVisible();
		await new_block_button.click();
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
