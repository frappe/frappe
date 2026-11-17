import { test, expect } from "../support";

const pathname = (page) => new URL(page.url()).pathname;

test.describe("Navigation", () => {
	test("Navigate to route with hash in document name", async ({ page, desk, api }) => {
		await page.goto("/app/website");
		await desk.ready();
		await api.insert_doc(
			"Client Script",
			{
				__newname: "ABC#123",
				dt: "User",
				script: "console.log('ran')",
				enabled: 0,
			},
			true
		);
		await page.goto(`/app/client-script/${encodeURIComponent("ABC#123")}`);
		await expect(page).toHaveTitle("ABC#123");
		await page.goBack();
		await expect(page).toHaveTitle("Website");
	});

	test("Navigate to previous page after login", async ({ page, desk }) => {
		await page.goto("/app/todo");
		await expect(
			page.locator(".page-head").getByTitle("To Do", { exact: true })
		).toBeVisible();
		await desk.clear_filters();
		await desk.logout();
		await page.reload();
		await page.getByRole("button", { name: "Login", exact: true }).click();
		await expect.poll(() => pathname(page)).toBe("/login");
		await desk.login();
		await page.reload();
		await expect.poll(() => pathname(page)).toBe("/app/todo");
	});
});
