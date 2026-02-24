const { test, expect } = require("@playwright/test");
const { login, logout } = require("../utils");

const adminPassword = process.env.ADMIN_PASSWORD || "admin";

test.describe("Login", () => {
	test.beforeEach(async ({ page }) => {
		// ensure logged-in so we can call logout via API
		await login(page);
		await page.goto("/");
		await logout(page);
		await page.goto("/login");
		await expect(page).toHaveURL(/\/login/);
	});

	test("greets with login screen", async ({ page }) => {
		await expect(page.locator(".page-card-head").first()).toContainText("Login");
	});

	test("validates password", async ({ page }) => {
		await page.locator("#login_email").fill("Administrator");
		await page.getByRole("button", { name: "Login" }).click();
		await expect(page).toHaveURL(/\/login/);
	});

	test("validates email", async ({ page }) => {
		await page.locator("#login_password").fill("qwe");
		await page.getByRole("button", { name: "Login" }).click();
		await expect(page).toHaveURL(/\/login/);
	});

	test("shows invalid login if incorrect credentials", async ({ page }) => {
		await page.locator("#login_email").fill("Administrator");
		await page.locator("#login_password").fill("qwer");

		await page.getByRole("button", { name: "Login" }).click();
		await expect(
			page.getByRole("button", { name: "Invalid Login. Try again." })
		).toBeVisible();
		await expect(page).toHaveURL(/\/login/);
	});

	test("logs in using correct credentials", async ({ page }) => {
		await page.locator("#login_email").fill("Administrator");
		await page.locator("#login_password").fill(adminPassword);

		await page.getByRole("button", { name: "Login" }).click();
		await expect(page).toHaveURL(/\/desk/);

		const user = await page.evaluate(() => window.frappe.session.user);
		expect(user).toBe("Administrator");
	});

	test("check redirect after login", async ({ page }) => {
		const payload = new URLSearchParams({
			uuid: "6fed1519-cfd8-4a2d-84a6-9a1799c7c741",
			encoded_string: "hello all",
			encoded_url: "http://test.localhost/callback",
			base64_string: "aGVsbG8gYWxs",
		});

		await logout(page);

		const redirectTo = "/me?" + payload.toString().replace(/\+/g, " ");
		await page.goto("/login?redirect-to=" + encodeURIComponent(redirectTo));

		await page.locator("#login_email").fill("Administrator");
		await page.locator("#login_password").fill(adminPassword);

		await page.getByRole("button", { name: "Login" }).click();

		const expectedFragment = "/me?" + payload.toString().replace(/\+/g, "%20");
		await expect(page).toHaveURL(
			new RegExp(expectedFragment.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
		);
	});
});
