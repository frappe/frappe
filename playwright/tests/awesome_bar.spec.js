import { test, expect, use_shared_page } from "../support";

async function search_awesomebar(page, text) {
	const search = page.locator("#navbar-search");
	await search.pressSequentially(text);
	await expect(
		page
			.locator(".awesomplete", { has: search })
			.getByRole("listbox")
			.locator("li", { hasText: `Search for ${text}` })
	).toBeVisible();
	return search;
}

async function awesomebar(page, text) {
	const search = await search_awesomebar(page, text);
	await search.press("ArrowDown");
	await search.press("Enter");
}

test.describe("Awesome Bar", () => {
	const shared = use_shared_page();

	test.beforeAll(async () => {
		const { page, desk } = shared;
		await page.goto("/app/website");
		await desk.ready();
	});

	test.beforeEach(async () => {
		const { page } = shared;
		await page.locator(".navbar .navbar-home").click();
		await expect(page.locator(".modal:visible")).toHaveCount(0);
		await page.locator("#navbar-search").click();
		await page.locator("#navbar-search").press("ControlOrMeta+a");
	});

	test.afterEach(async () => {
		const { page } = shared;
		// Escape only closes a dialog that has finished opening
		await page.waitForFunction(
			() => !frappe.msg_dialog?.is_visible || frappe.msg_dialog.display
		);
		await page.keyboard.press("Escape");
		await expect(page.locator(".modal:visible")).toHaveCount(0);
	});

	test("navigates to doctype list", async () => {
		const { page } = shared;
		const search = await search_awesomebar(page, "todo");
		await expect(
			page.locator(".awesomplete", { has: search }).getByRole("listbox")
		).toBeVisible();
		await search.press("Enter");
		await expect(page.locator(".title-text:visible")).toContainText("To Do");
		await expect(page).toHaveURL((url) => url.pathname === "/app/todo");
	});

	test("navigates to new form", async () => {
		const { page } = shared;
		const search = await search_awesomebar(page, "new blog post");
		await search.press("Enter");
		await expect(page.locator(".title-text:visible")).toHaveText("New Blog Post");
	});

	test("calculates math expressions", async () => {
		const { page, desk } = shared;
		await awesomebar(page, "55 + 32");
		await expect(desk.get_open_dialog().locator(".modal-title")).toContainText("Result");
		await expect(desk.get_open_dialog().locator(".msgprint")).toContainText("55 + 32 = 87");
	});
});
