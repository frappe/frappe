import { test, expect } from "../support";

test.describe("Msgprint", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/app");
		await desk.ready();
	});

	test("keeps the primary action of an earlier message in the same response", async ({
		page,
	}) => {
		await page.evaluate(() => {
			frappe.request.cleanup(
				{},
				{
					_server_messages: JSON.stringify([
						JSON.stringify({
							message: "Newly created user has no roles enabled.",
							primary_action: { label: "Add Roles" },
						}),
						JSON.stringify({ message: "Welcome email sent" }),
					]),
				}
			);
		});
		await expect(
			page.locator(".msgprint-dialog").getByRole("button", { name: "Add Roles" })
		).toBeVisible();
	});
});
