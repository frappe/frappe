import { test, expect } from "../support";

const CHECK_ALL = ".list-header-subject .list-subject .list-check-all";

test.describe("List View", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.setup_workflow");
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("Workflow", "Test ToDo", true);
	});

	test("Keep checkbox checked after Refresh", async ({ page, desk }) => {
		await desk.go_to_list("ToDo");
		await desk.clear_filters();
		await page.locator(CHECK_ALL).click();
		await page.locator("button[data-original-title='Reload List']").click();
		await expect(
			page.locator(".list-row-container .list-row-checkbox:checked").first()
		).toBeVisible();
	});

	test('enables "Actions" button', async ({ page, desk }) => {
		const actions = [
			"Approve",
			"Reject",
			"Export",
			"Assign To",
			"Clear Assignment",
			"Apply Assignment Rule",
			"Add Tags",
			"Print",
		];
		await desk.go_to_list("ToDo");
		await desk.clear_filters();
		await page.locator(CHECK_ALL).click();
		await page.getByRole("button", { name: "Actions", exact: true }).click();

		const menu_items = page.locator(".dropdown-menu li:visible .dropdown-item");
		await expect(menu_items).toHaveCount(8);
		for (const [index, action] of actions.entries()) {
			await expect(menu_items.nth(index)).toContainText(action);
		}

		const bulk_approval = page.waitForResponse(
			(res) =>
				res.request().method() === "POST" &&
				res.url().includes("api/method/frappe.model.workflow.bulk_workflow_approval")
		);
		await menu_items.filter({ hasText: "Approve" }).first().click();
		await bulk_approval;
		await desk.hide_dialog();
		await page.reload();
		await desk.clear_filters();
		await expect(
			page.locator(".list-row-container:visible", { hasText: "Approved" }).first()
		).toBeVisible();
	});

	test("flips sort order icon and title", async ({ page, desk }) => {
		await desk.go_to_list("ToDo");
		await desk.clear_filters();

		await page.evaluate(() => {
			const sort_selector = cur_list.sort_selector;
			sort_selector.set_value(sort_selector.sort_by, "desc");
		});

		const order = page.locator(".sort-selector .btn-order");
		await expect(order).toHaveAttribute("title", "descending");
		await expect(order.locator(".sort-order use")).toHaveAttribute(
			"href",
			"#icon-sort-descending"
		);

		await order.click();
		await expect(order).toHaveAttribute("data-value", "asc");
		await expect(order).toHaveAttribute("title", "ascending");
		await expect(order.locator(".sort-order use")).toHaveAttribute(
			"href",
			"#icon-sort-ascending"
		);
	});
});
