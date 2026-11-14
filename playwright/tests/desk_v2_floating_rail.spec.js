// The floating rail: parked off screen, opened from the window's edge on the navigation's side,
// pinned to dock it and unpinned to float it again.
import { test, expect, ADMIN_PASSWORD, TEST_USER } from "../support";
import { Api } from "../support/api";
import { site_url } from "../support/config";

const APP = "frappe";
const SAVE = "frappe.shell.arrangement.save_navigation_layout";
const RESET = "frappe.shell.arrangement.reset_arrangement";

test.describe("Desk v2 floating rail", () => {
	let api;
	let request;

	const setSide = (value) =>
		api.call("frappe.client.set_value", {
			doctype: "User",
			name: TEST_USER,
			fieldname: "navigation_side",
			value,
		});
	const reset = async (scope) => api.call(RESET, { container: "Rail", address: APP, scope });
	const records = async () =>
		(
			await api.get_list(
				"Rail",
				["name", "user", "navigation_layout"],
				[["app", "=", APP]]
			)
		).data;

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
		await reset("user");
		await reset("site");
		await setSide("");
		await api.call(SAVE, { app: APP, navigation_layout: "floating_rail", scope: "site" });
	});

	test.afterAll(async () => {
		await reset("user");
		await reset("site");
		await setSide("");
		await api.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
		await request.dispose();
	});

	test("parks the rail off screen, and opens it from the left edge", async ({ page }) => {
		await page.goto("/apps/desk/todo");
		const box = page.locator("[data-floating-rail]");
		await expect(box).toHaveAttribute("data-open", "false");
		await expect.poll(async () => (await box.boundingBox()).x + (await box.boundingBox()).width).toBeLessThan(0);

		await page.mouse.move(300, 300);
		await page.mouse.move(0, 300);
		await expect(box).toHaveAttribute("data-open", "true");
		await expect.poll(async () => (await box.boundingBox()).x).toBe(8);

		await page.mouse.move(700, 300);
		await expect(box).toHaveAttribute("data-open", "false");
	});

	test("carries the app menu and the avatar itself on a page with no sidebar", async ({ page }) => {
		await page.goto("/apps/desk/todo");
		const box = page.locator("[data-floating-rail]");
		await expect(box).toHaveAttribute("data-open", "false");
		await expect(page.locator('[data-slot="sidebar"]')).toHaveCount(0);

		await page.mouse.move(300, 300);
		await page.mouse.move(0, 300);
		await expect(box).toHaveAttribute("data-open", "true");
		await expect(box.locator('[data-key="app-menu"]')).toBeVisible();
		await expect(box.locator('[data-key="user-menu"]')).toBeVisible();
	});

	test("on the right, opens after a rest at the edge and not on a pass-through", async ({
		page,
	}) => {
		await setSide("end");
		await page.goto("/apps/desk/todo");
		const box = page.locator("[data-floating-rail]");
		const width = page.viewportSize().width;

		await page.mouse.move(width - 300, 300);
		await page.mouse.move(width - 1, 300);
		await page.mouse.move(width - 300, 300);
		await page.waitForTimeout(400);
		await expect(box).toHaveAttribute("data-open", "false");

		await page.mouse.move(width - 1, 300);
		await page.waitForTimeout(250);
		await expect(box).toHaveAttribute("data-open", "true");
		await expect.poll(async () => (await box.boundingBox()).x + (await box.boundingBox()).width).toBe(width - 8);
	});

	test("pins to dock the rail, keeps it docked on a reload, and unpins to float it again", async ({
		page,
	}) => {
		await page.goto("/apps/desk/todo");
		const box = page.locator("[data-floating-rail]");
		await expect(box).toHaveAttribute("data-open", "false");
		await page.mouse.move(300, 300);
		await page.mouse.move(0, 300);
		await expect(box).toHaveAttribute("data-open", "true");
		await box.locator("[data-key='pin-navigation']").click();

		const rail = page.locator('[data-slot="sidebar-rail"]');
		await expect(page.locator("[data-floating-rail]")).toHaveCount(0);
		await expect(rail).toBeVisible();
		await expect(rail.locator("[data-key='unpin-navigation']")).toBeVisible();
		expect((await records()).filter((r) => r.user)).toHaveLength(1);

		await page.reload();
		await expect(page.locator("[data-floating-rail]")).toHaveCount(0);
		await expect(rail.locator("[data-key='unpin-navigation']")).toBeVisible();

		await rail.locator("[data-key='unpin-navigation']").click();
		await expect(page.locator("[data-floating-rail]")).toHaveCount(1);
		await expect(page.locator("[data-key='unpin-navigation']")).toHaveCount(0);
		expect((await records()).filter((r) => r.user)).toHaveLength(0);
	});
});
