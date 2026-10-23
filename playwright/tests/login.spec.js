import { test, expect, ADMIN_PASSWORD, GUEST } from "../support";

test.describe("Login", () => {
	test.use({ storageState: GUEST });

	test.beforeEach(async ({ page }) => {
		await page.goto("/login");
		await expect(page).toHaveURL(/\/login$/);
	});

	test("greets with login screen", async ({ page }) => {
		await expect(page.locator(".page-card-head").first()).toContainText("Sign In");
	});

	test("validates password", async ({ page }) => {
		await page.locator("#login_email").fill("Administrator");
		await page.getByRole("button", { name: "Continue", exact: true }).click();
		await expect(page).toHaveURL(/\/login$/);
	});

	test("validates email", async ({ page }) => {
		await page.locator("#login_password").fill("qwe");
		await page.getByRole("button", { name: "Continue", exact: true }).click();
		await expect(page).toHaveURL(/\/login$/);
	});

	test("shows invalid login if incorrect credentials", async ({ page }) => {
		await page.locator("#login_email").fill("Administrator");
		await page.locator("#login_password").fill("qwer");

		await page.getByRole("button", { name: "Continue", exact: true }).click();
		await expect(page.locator(".login-error-banner:visible")).toContainText(
			"Invalid credentials, try again."
		);
		await expect(page).toHaveURL(/\/login$/);
	});

	test("logs in using correct credentials", async ({ page }) => {
		await page.locator("#login_email").fill("Administrator");
		await page.locator("#login_password").fill(ADMIN_PASSWORD);

		await page.getByRole("button", { name: "Continue", exact: true }).click();
		await expect(page).toHaveURL(/\/desk/);
		await expect
			.poll(() => page.evaluate(() => window.frappe?.session?.user))
			.toBe("Administrator");
	});

	test("check redirect after login", async ({ page }) => {
		const payload = new URLSearchParams({
			uuid: "6fed1519-cfd8-4a2d-84a6-9a1799c7c741",
			encoded_string: "hello all",
			encoded_url: "http://test.localhost/callback",
			base64_string: "aGVsbG8gYWxs",
		});

		await page.goto(
			"/login?redirect-to=/me?" + encodeURIComponent(payload.toString().replace("+", " "))
		);

		await page.locator("#login_email").fill("Administrator");
		await page.locator("#login_password").fill(ADMIN_PASSWORD);

		await page.getByRole("button", { name: "Continue", exact: true }).click();

		await expect(page).toHaveURL((url) =>
			url.href.includes("/me?" + payload.toString().replace("+", "%20"))
		);
	});
});
