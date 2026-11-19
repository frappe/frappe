// The sidebar-only navigation layout: no rail, one 15rem sidebar with the app's header and the person's footer.
import { test, expect, ADMIN_PASSWORD, TEST_USER } from "../support";
import { Api } from "../support/api";
import { site_url } from "../support/config";

const APP = "frappe";
const SAVE = "frappe.shell.arrangement.save_navigation_layout";
const RESET = "frappe.shell.arrangement.reset_arrangement";

test.describe("Desk v2 sidebar-only layout", () => {
	let api;
	let request;

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

	test.afterAll(async () => {
		await api.call(RESET, { container: "Rail", address: APP, scope: "user" });
		await api.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
		await request.dispose();
	});

	test("draws the rail and the sidebar by default", async ({ page }) => {
		await api.call(RESET, { container: "Rail", address: APP, scope: "user" });
		await page.goto("/apps/desk/todo");

		await expect(page.locator('[data-slot="sidebar-rail"]')).toBeVisible();
	});

	test("draws one sidebar and no rail once the layout is sidebar only", async ({ page }) => {
		await api.call(SAVE, { app: APP, navigation_layout: "sidebar_only", scope: "user" });
		await page.goto("/apps/desk/todo");

		const sidebar = page.locator('[data-slot="sidebar"]');
		await expect(sidebar).toBeVisible();
		await expect(page.locator('[data-slot="sidebar-rail"]')).toHaveCount(0);
		await expect(sidebar.locator('[data-key="app-menu"]')).toBeVisible();
		await expect(sidebar.locator('[data-key="palette-trigger"]')).toContainText("Search");
		await expect(sidebar.locator('[data-key="user-menu"]')).toBeVisible();
		await expect.poll(async () => (await sidebar.boundingBox()).width).toBe(240);
	});
});
