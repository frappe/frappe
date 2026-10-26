import { test, expect } from "../support";
import data_field_validation_doctype from "../fixtures/data_field_validation_doctype";

const doctype_name = data_field_validation_doctype.name;

test.describe("URL Data Field Input", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", data_field_validation_doctype, true);
	});

	test.beforeEach(async ({ desk }) => {
		await desk.new_form(doctype_name);
	});

	async function type_url(desk, value) {
		const input = desk.get_field("url");
		await input.clear();
		await input.pressSequentially(value);
		return input;
	}

	test.describe("URL Data Field Input ", () => {
		test("should not show URL link button without focus", async ({ page, desk }) => {
			const input = await type_url(desk, "https://frappe.io");
			await expect(page.locator(".link-btn")).toBeVisible();
			await input.blur();
			await expect(page.locator(".link-btn")).toBeHidden();
		});

		test("should show URL link button on focus", async ({ page, desk }) => {
			const input = await type_url(desk, "https://frappe.io");
			await input.blur();
			await expect(page.locator(".link-btn")).toBeHidden();
			await input.focus();
			await expect(page.locator(".link-btn")).toBeVisible();
		});

		test("should not show URL link button for invalid URL", async ({ page, desk }) => {
			await type_url(desk, "https://frappe.io");
			await expect(page.locator(".link-btn")).toBeVisible();
			await type_url(desk, "fuzzbuzz");
			await expect(page.locator(".link-btn")).toBeHidden();
		});

		test("should have valid URL link with target _blank", async ({ page, desk }) => {
			await type_url(desk, "https://frappe.io");
			await expect(page.locator(".link-btn .btn-open")).toHaveAttribute(
				"href",
				"https://frappe.io"
			);
			await expect(page.locator(".link-btn .btn-open")).toHaveAttribute("target", "_blank");
		});

		test("should inject anchor tag in read-only URL data field", async ({ page }) => {
			await expect(page.locator('[data-fieldname="read_only_url"] a')).toHaveAttribute(
				"target",
				"_blank"
			);
		});
	});
});
