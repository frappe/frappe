import { test, expect } from "../support";

test.describe("Grid Pagination", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_contact_phone_nos_records");
	});

	test.beforeEach(async ({ page }) => {
		await page.goto("/desk/contact/Test Contact");
	});

	const get_table = (page) => page.locator('.frappe-control[data-fieldname="phone_nos"]');

	test("creates pages for child table", async ({ page }) => {
		const table = get_table(page);
		await expect(table.locator(".current-page-number")).toHaveValue("1");
		await expect(table.locator(".total-page-number")).toContainText("20");
		await expect(table.locator(".grid-body .grid-row")).toHaveCount(50);
	});

	test("goes to the next and previous page", async ({ page }) => {
		const table = get_table(page);
		await table.locator(".next-page").click();
		await expect(table.locator(".current-page-number")).toHaveValue("2");
		await expect(table.locator(".grid-body .grid-row").first()).toHaveAttribute(
			"data-idx",
			"51"
		);
		await table.locator(".prev-page").click();
		await expect(table.locator(".current-page-number")).toHaveValue("1");
		await expect(table.locator(".grid-body .grid-row").first()).toHaveAttribute(
			"data-idx",
			"1"
		);
	});

	test("adds and deletes rows and changes page", async ({ page }) => {
		const table = get_table(page);
		await table.getByRole("button", { name: "Add row", exact: true }).click();
		await expect(
			table.locator(".grid-body .row-index").filter({ hasText: "1001" })
		).not.toHaveCount(0);
		await expect(table.locator(".current-page-number")).toHaveValue("21");
		await expect(table.locator(".total-page-number")).toContainText("21");
		await table.locator(".grid-body .grid-row .grid-row-check").click();
		await table.getByRole("button", { name: "Delete row", exact: true }).click();
		await expect(table.locator(".grid-body .row-index").last()).toContainText("1000");
		await expect(table.locator(".current-page-number")).toHaveValue("20");
		await expect(table.locator(".total-page-number")).toContainText("20");
	});

	test("deletes selected rows from every page", async ({ page }) => {
		const table = get_table(page);
		const rows = table.locator(".grid-body .grid-row");
		await expect(rows.first()).toHaveAttribute("data-idx", "1");
		const first_row = await rows.first().getAttribute("data-name");
		await rows.first().locator(".grid-row-check").click();
		await table.locator(".next-page").click();
		await expect(rows.last()).toHaveAttribute("data-idx", "100");
		const last_row = await rows.last().getAttribute("data-name");
		await rows.last().locator(".grid-row-check").click();
		await table.locator(".prev-page").click();
		await expect(table.locator(".current-page-number")).toHaveValue("1");
		await table.getByRole("button", { name: "Delete 2 rows", exact: true }).click();
		await expect
			.poll(() =>
				page.evaluate(
					(deleted) =>
						cur_frm.doc.phone_nos.filter((row) => deleted.includes(row.name)).length,
					[first_row, last_row]
				)
			)
			.toBe(0);
	});

	test("go to specific page, use up and down arrow, type characters, 0 page and more than existing page", async ({
		page,
	}) => {
		const table = get_table(page);
		const page_number = table.locator(".current-page-number");
		const go_to_page = async (value) => {
			await page_number.focus();
			await page_number.clear();
			await page_number.pressSequentially(value);
			await page_number.blur();
		};

		await go_to_page("17");
		await expect(
			table.locator(".grid-body .row-index").filter({ hasText: "801" })
		).not.toHaveCount(0);

		await page_number.press("ArrowUp");
		await page_number.press("ArrowUp");
		await expect(page_number).toHaveValue("19");

		await page_number.press("ArrowDown");
		await page_number.press("ArrowDown");
		await expect(page_number).toHaveValue("17");

		await go_to_page("700");
		await expect(page_number).toHaveValue("20");

		await go_to_page("0");
		await expect(page_number).toHaveValue("1");

		await go_to_page("abc");
		await expect(page_number).toHaveValue("1");
	});
});
