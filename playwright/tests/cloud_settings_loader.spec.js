import { test, expect } from "../support";

// Pilot hosts the Cloud Settings UI. Desk imports its ES runtime and falls back to the classic
// script on a pilot that serves no module, so the dialog opens on every pilot version.
const PILOT = "http://pilot.test/embed/cloud-settings";
const BUNDLE = { js: `${PILOT}/cloud-settings.js`, module: `${PILOT}/esm/cloud-settings.js` };
const SETTINGS = { site_name: "example.com", bundle: BUNDLE };

const MODULE = `export const mountCloudSettings = (settings) => {
	window.cloud_settings_mounted = ["module", settings.site_name];
};`;
const SCRIPT = `frappe.cloudSettings = { show: (settings) => {
	window.cloud_settings_mounted = ["script", settings.site_name];
} };`;

test.describe("Cloud Settings loader", () => {
	let requested;

	const serve = async (page, { module, script }) => {
		await page.unroute("http://pilot.test/**");
		await page.route("http://pilot.test/**", (route) => {
			const url = route.request().url();
			requested.push(url);
			const body = url.includes("/esm/") ? module : script;
			if (!body) return route.fulfill({ status: 404 });
			return route.fulfill({
				contentType: "text/javascript",
				headers: { "access-control-allow-origin": "*" },
				body,
			});
		});
	};

	const desktop = (page) =>
		page.waitForFunction(() => frappe.pages.desktop?.desktop_page?.load_cloud_settings);

	const open = (page) =>
		page.evaluate(async (settings) => {
			await frappe.pages.desktop.desktop_page.open_cloud_settings(settings);
			return window.cloud_settings_mounted;
		}, SETTINGS);

	test.beforeEach(async ({ page }) => {
		requested = [];
		await page.goto("/desk/desktop");
		await desktop(page);
	});

	test("mounts the ES runtime without fetching the classic script", async ({ page }) => {
		await serve(page, { module: MODULE, script: SCRIPT });

		expect(await open(page)).toEqual(["module", "example.com"]);
		expect(requested).toEqual([BUNDLE.module]);
	});

	test("falls back to the classic script when pilot serves no module", async ({ page }) => {
		await serve(page, { script: SCRIPT });

		expect(await open(page)).toEqual(["script", "example.com"]);
		expect(requested).toEqual([BUNDLE.module, BUNDLE.js]);
	});

	test("loads the runtime once for repeated opens", async ({ page }) => {
		await serve(page, { module: MODULE, script: SCRIPT });

		await open(page);
		await open(page);
		expect(requested).toEqual([BUNDLE.module]);
	});

	test("retries with fresh URLs after pilot fails", async ({ page }) => {
		await serve(page, {});
		expect(await open(page)).toBeUndefined();
		await expect(page.locator(".es-toast")).toContainText("Couldn't open Cloud settings");

		requested = [];
		await serve(page, { module: MODULE, script: SCRIPT });
		expect(await open(page)).toEqual(["module", "example.com"]);
		expect(requested).toHaveLength(1);
		expect(requested[0]).toMatch(/esm\/cloud-settings\.js\?_=\d+$/);
	});

	test("warms the classic script on hover when the module is missing", async ({ page }) => {
		await serve(page, { script: SCRIPT });

		await page.evaluate(
			(bundle) => frappe.pages.desktop.desktop_page.prefetch_cloud_settings(bundle),
			BUNDLE
		);
		await expect.poll(() => requested).toEqual([BUNDLE.module, BUNDLE.js]);
	});
});
