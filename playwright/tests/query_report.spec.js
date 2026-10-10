import { test, expect } from "../support";

const REPORT_PAGE = "#page-query-report";

async function click_report_menu_item(page, label) {
	await page.locator(`${REPORT_PAGE} .page-actions .menu-btn-group > button`).click();
	await page
		.locator('.es-menu [role="menuitem"]')
		.filter({ hasText: new RegExp(label) })
		.first()
		.click();
}

async function select_autocomplete(desk, fieldname, value) {
	const input = desk
		.get_open_dialog()
		.locator(`.control-input > .awesomplete > input[data-fieldname="${fieldname}"]`);
	await expect(input).toBeVisible();
	await input.clear();
	await input.pressSequentially(value, { delay: 150 });
	await input.press("Enter");
}

async function save_report(page, desk, report_name) {
	await click_report_menu_item(page, "Save");
	await expect(desk.get_open_dialog().locator(".modal-title")).toContainText("Save Report");

	const input = desk.get_open_dialog().locator('input[data-fieldname="report_name"]');
	await input.press("End");
	await input.pressSequentially(report_name, { delay: 100 });
	const saved = page.waitForResponse((res) =>
		res.url().includes("/api/method/frappe.desk.query_report.save_report")
	);
	await desk.get_open_dialog().getByRole("button", { name: "Submit", exact: true }).click();
	await saved;
}

async function open_sorting_report(page, result) {
	await page.route("**/api/method/frappe.desk.query_report.run*", (route) =>
		route.fulfill({
			json: {
				message: {
					columns: [
						{ fieldname: "value", label: "Value", fieldtype: "Int", width: 180 },
					],
					result,
				},
			},
		})
	);
	const report = page.waitForResponse((response) =>
		response.url().includes("/api/method/frappe.desk.query_report.run")
	);
	await page.goto("/desk/query-report/Test ToDo Report");
	await report;
	await expect(page.locator(".datatable")).toBeAttached();
}

async function sort_report(page, label) {
	await page
		.locator(".dt-header .dt-cell")
		.filter({ hasText: "Value" })
		.locator(".dt-dropdown__toggle")
		.click();
	await page.locator(".dt-dropdown__list-item").filter({ hasText: label }).click();
}

async function toggle_tree_row(page, value) {
	await page
		.locator(".dt-scrollable .dt-tree-node")
		.filter({ hasText: String(value) })
		.locator(".dt-tree-node__toggle")
		.click();
}

async function expect_row_order(page, expected) {
	await expect(
		page.locator(".dt-scrollable .dt-row .dt-cell:last-child .dt-cell__content")
	).toHaveText(expected.map(String));
}

async function expect_serial_numbers(page, count) {
	const serial_numbers = await page
		.locator(".dt-scrollable .dt-row .dt-cell:first-child .dt-cell__content")
		.allTextContents();
	expect(serial_numbers.map((number) => number.trim())).toEqual(
		Array.from({ length: count }, (_, index) => String(index + 1))
	);
}

test.describe("Query Report", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc(
			"Report",
			{
				report_name: "Test ToDo Report",
				ref_doctype: "ToDo",
				report_type: "Query Report",
				query: "select * from tabToDo",
			},
			true
		);
		await admin.create_records({
			doctype: "ToDo",
			description: "this is a test todo for query report",
		});
	});

	test("add custom column in report", async ({ page, desk }) => {
		await page.goto("/desk/query-report/Permitted Documents For User");

		await expect(page.locator(".page-form.flex")).toHaveCount(1, { timeout: 60000 });

		// set each filter in one go: typing it out makes the report run with partial values
		const input_user = page.locator(`${REPORT_PAGE} input[data-fieldname="user"]`);
		await input_user.fill("test@erpnext.com");
		await input_user.blur();
		const input_role = page.locator(`${REPORT_PAGE} input[data-fieldname="doctype"]`);
		await input_role.fill("Role");
		await input_role.blur();

		await expect(page.locator(".datatable")).toBeAttached();
		await click_report_menu_item(page, "Add Column");
		await expect(desk.get_open_dialog().locator(".modal-title")).toContainText("Add Column");
		await desk
			.get_open_dialog()
			.locator('select[data-fieldname="doctype"]')
			.selectOption("Role (Name)");
		await select_autocomplete(desk, "field", "Role Name");
		await select_autocomplete(desk, "insert_after", "Name");
		await desk.get_open_dialog().getByRole("button", { name: "Submit", exact: true }).click();

		await save_report(page, desk, "Test Report");
	});

	test("requires document type and field before adding a custom column", async ({
		page,
		desk,
	}) => {
		await page.goto("/desk/query-report/Test ToDo Report");

		await expect(page.locator(".datatable")).toBeAttached({ timeout: 60000 });
		await click_report_menu_item(page, "Add Column");
		await expect(desk.get_open_dialog().locator(".modal-title")).toContainText("Add Column");
		await desk.get_open_dialog().getByRole("button", { name: "Submit", exact: true }).click();

		const msgprint = page.locator(".msgprint");
		await expect(msgprint).toBeVisible();
		await expect(msgprint).toContainText("From Document Type");
		await expect(msgprint).toContainText("Field");
	});

	test("keeps tree rows grouped when sorting and expanding parents", async ({ page }) => {
		await open_sorting_report(page, [
			{ value: 7, indent: 0 },
			{ value: 1, indent: 1 },
			{ value: 8, indent: 1 },
			{ value: 3, indent: 0 },
			{ value: 4, indent: 1 },
			{ value: 5, indent: 2 },
			{ value: 6, indent: 2 },
			{ value: 2, indent: 1 },
		]);
		await expect_row_order(page, [7, 1, 8, 3, 4, 5, 6, 2]);

		await page.evaluate(() => {
			const row_manager = frappe.query_report.datatable.rowmanager;
			const refresh_rows = row_manager.refreshRows;
			window.tree_sort_draws = 0;
			row_manager.refreshRows = (...args) => {
				window.tree_sort_draws += 1;
				return refresh_rows(...args);
			};
		});
		await sort_report(page, "Sort Ascending");
		await expect_row_order(page, [3, 2, 4, 5, 6, 7, 1, 8]);
		await expect_serial_numbers(page, 8);
		expect(await page.evaluate(() => window.tree_sort_draws)).toBe(1);
		await toggle_tree_row(page, 7);
		await expect_row_order(page, [3, 2, 4, 5, 6, 7]);
		await toggle_tree_row(page, 7);
		await expect_row_order(page, [3, 2, 4, 5, 6, 7, 1, 8]);

		await page.evaluate(() => (window.tree_sort_draws = 0));
		await sort_report(page, "Sort Descending");
		await expect_row_order(page, [7, 8, 1, 3, 4, 6, 5, 2]);
		await expect_serial_numbers(page, 8);
		expect(await page.evaluate(() => window.tree_sort_draws)).toBe(1);
		await toggle_tree_row(page, 3);
		await expect_row_order(page, [7, 8, 1, 3]);
		await toggle_tree_row(page, 3);
		await expect_row_order(page, [7, 8, 1, 3, 4, 2]);
		await toggle_tree_row(page, 4);
		await expect_row_order(page, [7, 8, 1, 3, 4, 6, 5, 2]);

		await page.evaluate(() => (window.tree_sort_draws = 0));
		await sort_report(page, "Reset sorting");
		await expect_row_order(page, [7, 1, 8, 3, 4, 5, 6, 2]);
		await expect_serial_numbers(page, 8);
		expect(await page.evaluate(() => window.tree_sort_draws)).toBe(1);
	});

	test("sorts flat report rows without tree grouping", async ({ page }) => {
		await open_sorting_report(page, [{ value: 3 }, { value: 1 }, { value: 2 }]);
		await expect_row_order(page, [3, 1, 2]);
		await sort_report(page, "Sort Ascending");
		await expect_row_order(page, [1, 2, 3]);
		await sort_report(page, "Sort Descending");
		await expect_row_order(page, [3, 2, 1]);
	});

	const save_report_and_open = async (page, desk, report, update_name) => {
		await save_report(page, desk, update_name);

		await page.goto("/desk/query-report/" + report);
		await expect(page.locator(".datatable")).toBeAttached();
	};

	test("test multi level query report", async ({ page, desk }) => {
		await page.goto("/desk/query-report/Test ToDo Report");
		await expect(page.locator(".datatable")).toBeAttached();

		await save_report_and_open(page, desk, "Test ToDo Report 1", " 1");
		await save_report_and_open(page, desk, "Test ToDo Report 11", "1");
	});
});
