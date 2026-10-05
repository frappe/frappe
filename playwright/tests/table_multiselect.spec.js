import { test, expect } from "../support";

test.describe("Table MultiSelect", () => {
	const suffix = Math.random().toString().slice(2, 8);
	const name = "table multiselect" + suffix;
	const saved_rule = "table multiselect saved " + suffix;
	const selected_values =
		'.frappe-control[data-fieldname="users"] .form-control .tb-selected-value';

	const open_saved_rule = async (page, desk) => {
		await desk.go_to_list("Assignment Rule");
		await page.locator(".list-subject", { hasText: saved_rule }).locator("a").click();
		await expect(page.locator(selected_values)).toHaveCount(1);
	};

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("Assignment Rule", {
			name: saved_rule,
			document_type: "Web Page",
			description: "Automatic Assignment",
			assign_condition: 'status=="Open"',
			rule: "Round Robin",
			users: [{ user: "test@erpnext.com" }],
			assignment_days: [{ day: "Monday" }],
		});
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("Assignment Rule", name, true);
		await admin.remove_doc("Assignment Rule", saved_rule, true);
	});

	test("select value from multiselect dropdown", async ({ page, desk }) => {
		await desk.new_form("Assignment Rule");
		await desk.fill_field("__newname", name);
		await desk.fill_field("document_type", "Web Page");
		await page
			.locator(".section-head", { hasText: "Assignment Rules" })
			.first()
			.scrollIntoViewIfNeeded();
		await desk.fill_field("assign_condition", 'status=="Open"', "Code");
		const input = page.locator('input[data-fieldname="users"]');
		const dropdown = page.locator('input[data-fieldname="users"] + ul');
		await input.focus();
		await expect(dropdown).toBeVisible();
		await input.pressSequentially("test@erpnext", { delay: 100 });
		await expect(dropdown.locator("div[role='option']").first()).toContainText(
			"test@erpnext.com"
		);
		await input.press("Enter");
		const selected_value = page.locator(`${selected_values} .btn-link-to-form`);
		await expect(selected_value).toContainText("test@erpnext.com");

		const saved = page.waitForResponse(
			(res) =>
				res.request().method() === "POST" &&
				res.url().includes("/api/method/frappe.desk.form.save.savedocs")
		);
		await page.locator(".primary-action:visible").click();
		expect((await saved).status()).toBe(200);
		await expect(selected_value).toContainText("test@erpnext.com");
	});

	test("delete value using backspace", async ({ page, desk }) => {
		await open_saved_rule(page, desk);
		const input = page.locator('input[data-fieldname="users"]');
		await input.focus();
		await input.press("Backspace");
		await expect(page.locator(selected_values)).toHaveCount(0);
	});

	test("delete value using x", async ({ page, desk }) => {
		await open_saved_rule(page, desk);
		const existing_value = page.locator(selected_values);
		await existing_value.locator(".btn-remove").click();
		await expect(existing_value).toHaveCount(0);
	});

	test("navigate to selected value", async ({ page, desk }) => {
		await open_saved_rule(page, desk);
		const existing_value = page.locator(selected_values);
		await existing_value.locator(".btn-link-to-form").click();
		await expect(page).toHaveURL(/\/user\/test%40erpnext\.com/);
	});
});
