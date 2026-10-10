import { test, expect, use_shared_page } from "../support";

const TITLE = ".navbar-breadcrumbs:visible li:last-child";

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
	const shared = use_shared_page({
		teardown: async ({ page, desk }) => {
			await page.goto("/desk/todo");
			await desk.clear_filters();
		},
	});

	test.beforeAll(async () => {
		const { page, desk } = shared;
		await page.goto("/desk/todo");
		await desk.clear_filters();
		await page.goto("/desk/web-page");
		await desk.clear_filters();
		await page.goto("/desk/build");
		await desk.ready();
	});

	test.beforeEach(async () => {
		const { page } = shared;
		await page.keyboard.press("Escape");
		await expect(page.locator(".modal:visible")).toHaveCount(0);
		await page.locator(".body-sidebar .navbar-modal-search-mobile").click();
		await expect(page.locator("#navbar-search")).toBeFocused();
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

	test("opens awesome bar on click", async () => {
		await expect(shared.page.locator("#navbar-search")).toBeVisible();
	});

	test("navigates to doctype list", async () => {
		const { page } = shared;
		const search = await search_awesomebar(page, "todo");
		await expect(
			page.locator(".awesomplete", { has: search }).getByRole("listbox")
		).toBeVisible();
		await search.press("Enter");
		await expect(page.locator(TITLE)).toContainText("To Do");
		await expect(page).toHaveURL((url) => /\/todo$/.test(url.pathname));
	});

	test("navigates to another doctype, filter not bleeding", async () => {
		const { page } = shared;
		const search = await search_awesomebar(page, "web page");
		await search.press("Enter");
		await expect(page.locator(TITLE)).toContainText("Web Page");
		await expect(page).toHaveURL((url) => url.search === "");
	});

	test("navigates to new form", async () => {
		const { page } = shared;
		const search = await search_awesomebar(page, "new web page");
		await search.press("Enter");
		await expect(page.locator(TITLE)).toHaveText("New Web Page");
	});

	test("calculates math expressions", async () => {
		const { page, desk } = shared;
		await awesomebar(page, "55 + 32");
		await expect(desk.get_open_dialog().locator(".modal-title")).toContainText("Result");
		await expect(desk.get_open_dialog().locator(".msgprint")).toContainText("55 + 32 = 87");
	});

	test("support number formats in math expressions", async () => {
		const { page, desk } = shared;
		await page.evaluate(() => {
			frappe.boot.sysdefaults.number_format = "#,###.##";
		});
		await awesomebar(page, "1,250.2 + 1,250.2");
		await expect(desk.get_open_dialog().locator(".modal-title")).toContainText("Result");
		await expect(desk.get_open_dialog().locator(".msgprint")).toContainText(
			"1,250.2 + 1,250.2 = 2,500.4"
		);
		await desk.hide_dialog();

		await page.locator(".body-sidebar .navbar-modal-search-mobile").click();
		await page.evaluate(() => {
			frappe.boot.sysdefaults.number_format = "#.###,##";
		});
		await awesomebar(page, "1.500,2 + 1.500,2");
		await expect(desk.get_open_dialog().locator(".modal-title")).toContainText("Result");
		await expect(desk.get_open_dialog().locator(".msgprint")).toContainText(
			"1.500,2 + 1.500,2 = 3.000,4"
		);
	});
});

test.describe("Awesome Bar page results", () => {
	const routes = (results) => results.map((r) => r.route.join("/"));

	test("leaves system pages out of page results", async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await desk.ready();

		const found = await page.evaluate(() => ({
			system: frappe.search.utils.get_pages("profile"),
			regular: frappe.search.utils.get_pages("dashboard"),
		}));
		expect(routes(found.system)).not.toContain("profile");
		expect(routes(found.regular)).toContain("dashboard-view");
	});

	test("leaves visited system pages out of recent results", async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await desk.ready();
		for (const route of ["profile", "dashboard-view"]) {
			await page.evaluate((route) => frappe.set_route(route), route);
			await page.waitForFunction(
				(route) => frappe.route_history.some((r) => r[0] === route),
				route
			);
		}

		const found = await page.evaluate(() => ({
			system: frappe.search.utils.get_recent_pages("profile"),
			regular: frappe.search.utils.get_recent_pages("dashboard"),
		}));
		expect(routes(found.system)).not.toContain("profile");
		expect(routes(found.regular)).toContain("dashboard-view");
	});
});
