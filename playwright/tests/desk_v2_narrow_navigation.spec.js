// The navigation from 768 to 1023 px: the rail stays with its sidebar over the page, and the other layouts
// give a menu button that opens a drawer from the navigation's side.
import { test, expect, ADMIN_PASSWORD, TEST_USER } from "../support";
import { Api } from "../support/api";
import { site_url } from "../support/config";

const APP = "frappe";
const SAVE = "frappe.shell.arrangement.save_navigation_layout";
const RESET = "frappe.shell.arrangement.reset_arrangement";

test.describe("Desk v2 narrow navigation", () => {
	test.use({ viewport: { width: 820, height: 900 } });

	let api;
	let request;

	const setSide = (value) =>
		api.call("frappe.client.set_value", {
			doctype: "User",
			name: TEST_USER,
			fieldname: "navigation_side",
			value,
		});
	const reset = () => api.call(RESET, { container: "Rail", address: APP, scope: "user" });

	test.beforeAll(async ({ playwright }, workerInfo) => {
		request = await playwright.request.newContext({
			baseURL: site_url(workerInfo.parallelIndex),
		});
		const res = await request.post("/api/method/login", {
			data: { usr: TEST_USER, pwd: ADMIN_PASSWORD },
		});
		expect(res.status(), `login as ${TEST_USER}: ${await res.text()}`).toBe(200);
		api = new Api(request);
		await api.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
	});

	test.beforeEach(async () => {
		await reset();
		await setSide("");
	});

	test.afterAll(async () => {
		await reset();
		await setSide("");
		await api.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
		await request.dispose();
	});

	test("rail + sidebar keeps the rail and has no menu button", async ({ page }) => {
		await page.goto("/apps/desk/todo");

		await expect(page.locator('[data-slot="sidebar-rail"]')).toBeVisible();
		await expect(page.locator('[data-key="open-navigation"]')).toHaveCount(0);
	});

	test("a drawer opens from the menu button and closes on Escape and on the scrim", async ({
		page,
	}) => {
		await api.call(SAVE, { app: APP, navigation_layout: "sidebar_only", scope: "user" });
		await page.goto("/apps/desk/todo");

		await expect(page.locator('[data-slot="sidebar-rail"]')).toHaveCount(0);
		const button = page.locator('[data-key="open-navigation"]');
		await expect(button).toBeVisible();
		// The button shares the page's left gutter.
		await expect.poll(async () => Math.round((await button.boundingBox()).x)).toBe(20);

		await button.click();
		const drawer = page.locator("[data-navigation-drawer]");
		await expect(drawer).toBeVisible();
		await expect.poll(async () => (await drawer.boundingBox()).x).toBe(0);
		await expect(drawer.locator('[data-key="palette-trigger"]')).toContainText("Search");

		await page.keyboard.press("Escape");
		await expect(drawer).toHaveCount(0);

		await button.click();
		await expect(drawer).toBeVisible();
		await page.locator("[data-navigation-drawer-scrim]").click({ position: { x: 790, y: 400 } });
		await expect(drawer).toHaveCount(0);
	});

	test("a navigation on the right: the button and the drawer move to the right edge", async ({
		page,
	}) => {
		await api.call(SAVE, { app: APP, navigation_layout: "sidebar_only", scope: "user" });
		await setSide("end");
		await page.goto("/apps/desk/todo");

		const button = page.locator('[data-key="open-navigation"]');
		await expect(button).toBeVisible();
		await expect
			.poll(async () => {
				const { x, width } = await button.boundingBox();
				return Math.round(820 - (x + width));
			})
			.toBe(20);

		await button.click();
		const drawer = page.locator("[data-navigation-drawer]");
		await expect(drawer).toBeVisible();
		await expect
			.poll(async () => {
				const { x, width } = await drawer.boundingBox();
				return Math.round(x + width);
			})
			.toBe(820);
	});
});
