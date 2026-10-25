import { test, expect } from "../support";

test.describe("Msgprint", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await desk.ready();
	});

	test("keeps an open message when the response carries only toasts", async ({ page }) => {
		await page.evaluate(() => {
			frappe.msgprint({ message: "client message", title: "client title" });
			frappe.request.cleanup(
				{},
				{
					_server_messages: JSON.stringify([
						JSON.stringify({ message: "Saved", alert: 1 }),
					]),
				}
			);
		});
		await expect(page.locator(".msgprint-dialog")).toBeVisible();
		await expect(page.locator(".msgprint")).toContainText("client message");
	});

	test("clears an open message before showing a server message", async ({ page }) => {
		await page.evaluate(() => {
			frappe.msgprint({ message: "client message", title: "client title" });
			frappe.request.cleanup(
				{},
				{
					_server_messages: JSON.stringify([
						JSON.stringify({ message: "server message" }),
					]),
				}
			);
		});
		await expect(page.locator(".msgprint")).toContainText("server message");
		await expect(page.locator(".msgprint")).not.toContainText("client message");
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
