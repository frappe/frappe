import { test, expect } from "../support";

const PAYLOAD =
	'Line one<br><i>slanted</i> <a href="https://frappe.io/docs">guide</a>' +
	"<script>window.__descriptionScript = 1</script>" +
	'<img src="x" onerror="window.__descriptionScript = 2">';

const SETTER = {
	doctype_or_field: "DocField",
	doc_type: "System Settings",
	field_name: "session_expiry",
	property: "description",
	property_type: "Small Text",
	value: PAYLOAD,
};

test.describe("Desk v2 settings field descriptions", () => {
	let setter;

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
		setter = await admin.insert_doc("Property Setter", SETTER);
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("Property Setter", setter?.name, true);
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	test("draws a description as sanitised HTML", async ({ page }) => {
		await page.goto("/apps/desk/todo#settings/desk/system");
		const dialog = page.getByRole("dialog");
		const row = dialog.locator('[data-fieldname="session_expiry"]');
		await expect(row.getByText("slanted")).toBeAttached();

		await expect(row.locator("br")).toHaveCount(1);
		await expect(row.locator("i")).toHaveText("slanted");
		await expect(row.locator("script")).toHaveCount(0);
		await expect(row.locator("[onerror]")).toHaveCount(0);
		await expect(row).not.toContainText("<br>");

		const link = row.getByRole("link", { name: "guide" });
		await expect(link).toHaveAttribute("target", "_blank");
		await expect(link).toHaveAttribute("rel", "noopener noreferrer");
	});

	test("draws a long field's stored description as HTML", async ({ page }) => {
		await page.goto("/apps/desk/todo#settings/desk/system");
		const dialog = page.getByRole("dialog");
		const row = dialog.locator('[data-fieldname="allowed_file_extensions"]');
		await expect(row.getByText("Provide a list of allowed file extensions")).toBeAttached();

		await expect(row.locator("br")).toHaveCount(3);
		await expect(row).not.toContainText("<br>");

		const plain = dialog.locator('[data-fieldname="email_footer_address"]');
		await expect(
			plain.getByText("Your organization name and address for the email footer.", {
				exact: true,
			})
		).toBeAttached();
	});
});
