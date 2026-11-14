import { test, expect } from "../support";

test.describe("Navigation side in the settings dialog", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.set_value("User", "frappe@example.com", { navigation_side: "" });
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
	});

	test.afterAll(async ({ admin }) => {
		await admin.set_value("User", "frappe@example.com", { navigation_side: "" });
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	test("picking Right draws the rail on the right, and Site default brings them back", async ({
		page,
	}) => {
		await page.goto("/apps/desk/todo#settings/desk/profile");
		const dialog = page.getByRole("dialog");
		const side = dialog.locator('[data-fieldname="navigation_side"] button[role="combobox"]');
		const rail = page.locator("nav").first();
		const width = () => page.evaluate(() => document.documentElement.clientWidth);

		await expect(side).toContainText("Site default (Left)");
		expect((await rail.boundingBox()).x).toBeLessThan(60);

		await side.click();
		await page.getByRole("option", { name: "Right", exact: true }).click();

		await expect.poll(async () => (await rail.boundingBox()).x).toBeGreaterThan((await width()) - 60);

		await side.click();
		await page.getByRole("option", { name: "Site default (Left)" }).click();
		await expect.poll(async () => (await rail.boundingBox()).x).toBeLessThan(60);
	});
});
