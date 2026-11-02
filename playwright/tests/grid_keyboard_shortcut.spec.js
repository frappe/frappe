import { test, expect } from "../support";

async function add_new_row_in_grid(page, shortcut_keys) {
	const table = page.locator('.frappe-control[data-fieldname="email_ids"]');
	const cell = table.locator('.grid-body [data-fieldname="email_id"]').first();
	await cell.click();
	await expect(cell.locator("input")).toBeFocused();
	await page.keyboard.press(shortcut_keys);
}

test.describe("Grid Keyboard Shortcut", () => {
	const total_count = 0;
	let contact_email_name = null;

	test.beforeEach(async ({ page, desk }) => {
		await desk.new_form("Contact");
		const table = page.locator('.frappe-control[data-fieldname="email_ids"]');
		await table.locator(".grid-add-row").click();
		// as new names uses hash instead of numbers get row's data-name dynamically.
		contact_email_name = await table
			.locator(".grid-body .grid-row")
			.first()
			.getAttribute("data-name");
	});

	test("Insert new row at the end", async ({ page }) => {
		await add_new_row_in_grid(page, "Control+Shift+ArrowDown");
		await expect(page.locator(`[data-name="${contact_email_name}"]`).first()).toHaveAttribute(
			"data-idx",
			`${total_count + 1}`
		);
	});

	test("Insert new row at the top", async ({ page }) => {
		await add_new_row_in_grid(page, "Control+Shift+ArrowUp");
		await expect(page.locator(`[data-name="${contact_email_name}"]`).first()).toHaveAttribute(
			"data-idx",
			"2"
		);
	});

	test("Insert new row below", async ({ page }) => {
		await add_new_row_in_grid(page, "Control+ArrowDown");
		await expect(page.locator(`[data-name^="${contact_email_name}"]`).first()).toHaveAttribute(
			"data-idx",
			"1"
		);
	});

	test("Insert new row above", async ({ page }) => {
		await add_new_row_in_grid(page, "Control+ArrowUp");
		await expect(page.locator(`[data-name^="${contact_email_name}"]`).first()).toHaveAttribute(
			"data-idx",
			"2"
		);
	});
});
