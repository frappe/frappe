import { test, expect } from "../support";

const HIGHLIGHTED = /(^|\s)driver-highlighted-element(\s|$)/;

const open_test_form_tour = async (page) => {
	await page.goto("/desk/form-tour/Test Form Tour");
	const show_tour = page.getByRole("button", { name: "Show Tour", exact: true });
	await expect(show_tour).toBeVisible();
	await show_tour.click();
	await expect(page).toHaveURL(/\/desk\/contact/);
};

test.describe.skip("Form Tour", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_form_tour");
	});

	test("jump to a form tour", async ({ page }) => {
		await open_test_form_tour(page);
	});

	test("navigates a form tour", async ({ page, desk }) => {
		await open_test_form_tour(page);

		const driver = page.locator(".frappe-driver");
		await expect(driver).toBeVisible();
		const first_name = page.locator('.frappe-control[data-fieldname="first_name"]');
		await expect(first_name).toHaveClass(HIGHLIGHTED);
		const next_btn = driver.getByRole("button", { name: "Next", exact: true });

		await next_btn.click();
		await expect(first_name).toHaveClass(HIGHLIGHTED);

		await desk.fill_field("first_name", "Test Name", "Data");
		await expect.poll(() => page.evaluate(() => cur_frm.doc.first_name)).toBe("Test Name");
		await next_btn.click();

		const last_name = page.locator('.frappe-control[data-fieldname="last_name"]');
		await expect(last_name).toHaveClass(HIGHLIGHTED);

		await desk.fill_field("last_name", "Test Last Name", "Data");
		await expect.poll(() => page.evaluate(() => cur_frm.doc.last_name)).toBe("Test Last Name");
		await next_btn.click();

		const phone_nos = page.locator('.frappe-control[data-fieldname="phone_nos"]');
		await expect(phone_nos).toHaveClass(HIGHLIGHTED);

		await next_btn.click();

		const add_row = phone_nos.locator(".grid-add-row");
		await expect(add_row).toHaveClass(HIGHLIGHTED);

		await add_row.click();

		const phone = page.locator('.grid-row-open .frappe-control[data-fieldname="phone"]');
		await expect(phone).toHaveClass(HIGHLIGHTED);
		const field = await desk.fill_table_field("phone_nos", "1", "phone", "1234567890");
		await field.blur();

		await expect(page.locator(".driver-popover-title")).toContainText("Test Title 4");
		await next_btn.click();
		await page.locator(".grid-row-open .grid-collapse-row").click();

		await expect(page.locator(".primary-action:visible")).toHaveClass(HIGHLIGHTED);
		await expect(driver.getByRole("button", { name: "Save", exact: true })).toBeVisible();
	});
});
