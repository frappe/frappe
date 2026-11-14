// The phone navigation below 768 px: a tab bar at the foot, no rail and no sidebar, and a bottom sheet of tiles.
import { test, expect, ADMIN_PASSWORD, TEST_USER } from "../support";
import { Api } from "../support/api";
import { site_url } from "../support/config";

test.describe("Desk v2 phone navigation", () => {
	test.use({ viewport: { width: 390, height: 844 } });

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
		await api.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
		await request.dispose();
	});

	test("draws a tab bar at the foot and no rail or sidebar", async ({ page }) => {
		await page.goto("/apps/desk/todo");

		const bar = page.locator("[data-phone-nav]");
		await expect(bar).toBeVisible();
		await expect(bar).toContainText("Menu");
		await expect(bar).toContainText("Search");
		await expect(bar).toContainText("You");
		await expect(page.locator('[data-slot="sidebar-rail"]')).toHaveCount(0);
		await expect(page.locator('[data-slot="sidebar"]')).toHaveCount(0);
		const { y, height } = await bar.boundingBox();
		expect(Math.round(y + height)).toBe(844);
	});

	test("Menu opens a sheet of tiles and a tile that navigates closes it", async ({ page }) => {
		await page.goto("/apps/desk/todo");
		await page.locator("[data-phone-nav]").getByText("Menu").click();

		const tiles = page.locator("[data-phone-tiles] [data-key] button");
		await expect(tiles.first()).toBeVisible();
		const { width, height } = await tiles.first().boundingBox();
		expect([Math.round(width), Math.round(height)]).toEqual([36, 36]);

		const before = page.url();
		await tiles.nth(1).click();
		await expect(page.locator("[data-phone-sheet]")).toHaveCount(0);
		expect(page.url()).not.toBe(before);
	});

	test("a bottom toaster stands above the tab bar, past sonner's own 600px rule", async ({
		page,
	}) => {
		await page.goto("/apps/desk/todo");
		await expect(page.locator("[data-phone-nav]")).toBeVisible();

		const bottom = await page.evaluate(() => {
			const toaster = document.createElement("ol");
			toaster.setAttribute("data-sonner-toaster", "");
			toaster.setAttribute("data-y-position", "bottom");
			toaster.setAttribute("data-x-position", "right");
			document.body.append(toaster);
			return getComputedStyle(toaster).bottom;
		});

		// The 16px mobile offset plus the tab bar's measured height.
		const { height } = await page.locator("[data-phone-nav]").boundingBox();
		expect(parseFloat(bottom)).toBeCloseTo(16 + height, 0);
	});
});
