import { test, expect } from "../support";
import doctype_with_tab_break from "../fixtures/doctype_with_tab_break";

const doctype_name = doctype_with_tab_break.name;

test.describe("Form Tab Break", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", doctype_with_tab_break, true);
	});

	test("Should switch tab and open correct tabs on validation error", async ({ page, desk }) => {
		await desk.new_form(doctype_name);
		const form = page.locator(".page-container:visible .form-layout");
		const save_button = page.getByRole("button", { name: "Save", exact: true });

		await page.getByRole("tab", { name: "Tab 2", exact: true }).click();
		await expect(form.getByText("Phone", { exact: true })).toBeVisible();
		await page.getByRole("tab", { name: "Details", exact: true }).click();
		await expect(form.getByText("Name", { exact: true })).toBeVisible();

		await desk.fill_field("username", "Test");
		await expect.poll(() => page.evaluate(() => cur_frm.doc.username)).toBe("Test");
		await save_button.click();
		await expect(page.getByText("Missing Fields", { exact: true })).toBeVisible();
		await desk.hide_dialog();
		await expect(form.getByText("Phone", { exact: true })).toBeVisible();
		await desk.fill_field("phone", "12345678");
		await expect.poll(() => page.evaluate(() => cur_frm.doc.phone)).toBe("12345678");
		await save_button.click();
		await expect(page.locator("body")).not.toHaveAttribute("data-route", /\/new-/);

		await page.locator(".form-tabs > .nav-item").nth(0).click();
		await expect(form.getByText("Profile", { exact: true })).toBeVisible();
	});
});
