import { test, expect } from "../support";

async function jump_to_field(page, field_label) {
	await page.keyboard.press("Escape");
	await page.keyboard.press("Control+j");

	await page.locator(".modal input[type='text']").first().focus();
	await page.keyboard.type(field_label);
	await expect(
		page.locator(".modal:visible [role='listbox'] li", { hasText: field_label }).first()
	).toBeVisible();
	await page.keyboard.press("Enter");
	await page.getByRole("button", { name: "Go", exact: true }).click();
}

test.describe("Form", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_contact_records");
	});

	test("create a new form", async ({ page, desk }) => {
		await desk.new_form("ToDo");
		const description = desk.get_field("description", "Text Editor");
		await description.pressSequentially("this is a test todo");
		await expect
			.poll(() => page.evaluate(() => cur_frm.doc.description))
			.toContain("this is a test todo");
		await expect(page.locator(".page-title:visible")).toContainText("Not Saved");

		const saved = page.waitForResponse(
			(res) =>
				res.request().method() === "POST" &&
				res.url().includes("api/method/frappe.desk.form.save.savedocs")
		);
		await page.locator(".primary-action:visible").click();
		expect((await saved).status()).toBe(200);

		await desk.go_to_list("ToDo");
		await desk.clear_filters();
		await expect(page.locator(".page-head:visible").getByTitle("To Do")).toBeAttached();
		await expect(
			page.locator(".list-row", { hasText: "this is a test todo" }).first()
		).toBeVisible();
	});

	test("navigates between documents with child table list filters applied", async ({
		page,
		desk,
	}) => {
		await page.goto("/desk/contact");

		await desk.clear_filters();
		const name_filter = page.locator('.standard-filter-section [data-fieldname="name"] input');
		await name_filter.pressSequentially("Test Form Contact 3");
		await name_filter.blur();
		await desk.click_listview_row_item_with_text("Test Form Contact 3");

		await page.goto("/desk/contact");
		await desk.clear_filters();
	});

	test("validates behaviour of Data options validations in child table", async ({
		page,
		desk,
	}) => {
		await page.goto("/desk/contact/new");
		await desk.fill_field("company_name", "Test Company");

		const table = page.locator('.frappe-control[data-fieldname="email_ids"]');
		await table.locator("button.grid-add-row").click();
		const row1 = table.locator('[data-idx="1"]');
		await row1.click();
		const email_input1 = row1.locator("input.input-with-feedback.form-control");
		await email_input1.pressSequentially("website.in");

		await table.locator("button.grid-add-row").click();
		const row2 = table.locator('[data-idx="2"]');
		await row2.click();
		const email_input2 = row2.locator("input.input-with-feedback.form-control");
		await email_input2.pressSequentially("user@email.com");

		await row1.click();
		await expect(email_input1).toHaveClass(/invalid/);

		await row2.click();
		await expect(email_input2).not.toHaveClass(/invalid/);
	});

	test("Jump to field in collapsed section", async ({ page, desk }) => {
		await desk.new_form("User");

		await jump_to_field(page, "Location");
		await expect(desk.get_field("location")).toBeFocused();
		await page.keyboard.type("Bermuda");
		await page.keyboard.press("Escape");

		await expect(desk.get_field("location")).toHaveValue("Bermuda");
	});

	test("update docfield property using set_df_property in child table", async ({ page }) => {
		await page.goto("/desk/contact/Test Form Contact 1");

		const table = page.locator('.frappe-control[data-fieldname="phone_nos"]');
		const table_form = page.locator(".grid-row-open");
		const is_primary_phone = table_form.locator(
			'.frappe-control[data-fieldname="is_primary_phone"]'
		);
		const set_hidden = async (hidden) => {
			const cdn = await table.locator('[data-idx="1"]').getAttribute("data-name");
			await page.evaluate(
				([hidden, cdn]) =>
					cur_frm.set_df_property(
						"phone_nos",
						"hidden",
						hidden,
						"Contact Phone",
						"is_primary_phone",
						cdn
					),
				[hidden, cdn]
			);
		};

		await set_hidden(1);
		await table.locator('[data-idx="1"] .btn-open-row').click();
		await expect(is_primary_phone).toBeHidden();
		await table_form.locator(".grid-footer-toolbar").click();

		await table.locator('[data-idx="1"] .btn-open-row').click();
		await set_hidden(0);
		await expect(is_primary_phone).toBeVisible();
		await table_form.locator(".grid-footer-toolbar").click();
	});
});
