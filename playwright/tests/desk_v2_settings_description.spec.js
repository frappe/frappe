import { test, expect } from "../support";

const PAYLOAD =
	'Line one<br><i>slanted</i> <a href="https://frappe.io/docs" target="_self" rel="opener">guide</a>' +
	'<a href="javascript:window.__descriptionScript = 3">unsafe</a>' +
	"<script>window.__descriptionScript = 1</script>" +
	'<img src="x" onerror="window.__descriptionScript = 2">';

const SETTERS = [
	// A short row draws its description through SettingsRow's slot.
	{ field_name: "session_expiry", property_type: "Small Text", value: PAYLOAD },
	// A long row draws its own.
	{ field_name: "allowed_file_extensions", property_type: "Small Text", value: PAYLOAD },
	{
		field_name: "email_footer_address",
		property_type: "Small Text",
		value: "Plain footer text.",
	},
];

test.describe("Desk v2 settings field descriptions", () => {
	const created = [];

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
		for (const setter of SETTERS) {
			created.push(
				await admin.insert_doc("Property Setter", {
					doctype_or_field: "DocField",
					doc_type: "System Settings",
					property: "description",
					...setter,
				})
			);
		}
	});

	test.afterAll(async ({ admin }) => {
		for (const setter of created) {
			await admin.remove_doc("Property Setter", setter.name, true);
		}
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	for (const [kind, fieldname] of [
		["short", "session_expiry"],
		["long", "allowed_file_extensions"],
	]) {
		test(`draws a ${kind} row's description as sanitised HTML`, async ({ page }) => {
			await page.goto("/apps/desk/todo#settings/desk/system");
			const row = page.getByRole("dialog").locator(`[data-fieldname="${fieldname}"]`);
			await expect(row.getByText("slanted")).toBeAttached();

			await expect(row.locator("br")).toHaveCount(1);
			await expect(row.locator("i")).toHaveText("slanted");
			await expect(row.locator("script")).toHaveCount(0);
			await expect(row.locator("[onerror]")).toHaveCount(0);
			await expect(row).not.toContainText("<br>");
			expect(await page.evaluate(() => window.__descriptionScript)).toBeUndefined();

			const link = row.getByRole("link", { name: "guide" });
			await expect(link).toHaveAttribute("href", "https://frappe.io/docs");
			await expect(link).toHaveAttribute("target", "_blank");
			await expect(link).toHaveAttribute("rel", "noopener noreferrer");
			await expect(row.getByText("unsafe")).not.toHaveAttribute("href", /javascript:/);
		});
	}

	test("draws a plain-text description as it is", async ({ page }) => {
		await page.goto("/apps/desk/todo#settings/desk/system");
		const row = page.getByRole("dialog").locator('[data-fieldname="email_footer_address"]');
		await expect(row.getByText("Plain footer text.", { exact: true })).toBeAttached();
	});
});
