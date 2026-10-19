import { test, expect } from "../support";

const SAVE_USER_DOCK = "frappe.desk.doctype.dock.dock.save_user_dock";
const EMAIL_LANDING = "/desk/email/email-account";

const sidebar_row = (link_to, hidden = 0) => ({ link_type: "Sidebar", link_to, hidden });
const url_row = { link_type: "URL", url: "https://example.com", hidden: 0 };

async function open_desk(page, desk) {
	await page.goto("/desk/todo");
	await desk.ready();
}

async function save_user_dock(page, desk, api, rows) {
	await api.call(SAVE_USER_DOCK, { app: "frappe", items: JSON.stringify(rows) });
	await open_desk(page, desk);
}

function landing(page, app) {
	return page.evaluate((app) => frappe.app.sidebar.app_landing_route(app), app);
}

function framework_landing(page) {
	return page.evaluate(() =>
		frappe.app.sidebar.app_landing_route(
			frappe.boot.app_data.find((app) => app.app_name === "frappe")
		)
	);
}

async function framework_tile_href(page) {
	await page.evaluate(() => frappe.set_route("desktop"));
	const tile = page.locator(".desktop-icon", { hasText: "Framework" }).locator(".icon-title");
	await expect(tile).toBeVisible();
	return tile.getAttribute("href");
}

test.describe("Where an app's icon leads", () => {
	test.beforeEach(async ({ page, desk }) => {
		await open_desk(page, desk);
	});

	test.afterEach(async ({ api }) => {
		await api.call(SAVE_USER_DOCK, { app: "frappe", items: "[]" });
	});

	test("follows the first entry of the user's dock", async ({ page, desk, api }) => {
		await save_user_dock(page, desk, api, [sidebar_row("Email"), sidebar_row("Build")]);

		expect(await framework_landing(page)).toBe(EMAIL_LANDING);
		expect(await framework_tile_href(page)).toBe(EMAIL_LANDING);
	});

	test("passes over an entry the user hid", async ({ page, desk, api }) => {
		await save_user_dock(page, desk, api, [sidebar_row("Build", 1), sidebar_row("Email")]);

		expect(await framework_landing(page)).toBe(EMAIL_LANDING);
		expect(await framework_tile_href(page)).toBe(EMAIL_LANDING);
	});

	test("passes over an entry that opens nothing for this user", async ({ page }) => {
		const route = await landing(page, {
			app_name: "frappe-like",
			app_route: "/desk/build",
			dock: [sidebar_row("No Such Module"), sidebar_row("Email")],
		});

		expect(route).toBe(EMAIL_LANDING);
	});

	test("passes over a URL entry", async ({ page }) => {
		const route = await landing(page, {
			app_name: "frappe-like",
			app_route: "/desk/build",
			dock: [url_row, sidebar_row("Email")],
		});

		expect(route).toBe(EMAIL_LANDING);
	});

	test("passes over a sidebar whose first item leaves the desk", async ({ page }) => {
		const route = await page.evaluate(
			([url_row, dock]) => {
				frappe.boot.module_sidebars["Outside"] = {
					name: "Outside",
					items: [{ type: "Link", ...url_row }],
				};
				return frappe.app.sidebar.app_landing_route({
					app_name: "frappe-like",
					app_route: "/desk/build",
					dock,
				});
			},
			[url_row, [sidebar_row("Outside"), sidebar_row("Email")]]
		);

		expect(route).toBe(EMAIL_LANDING);
	});

	test("falls back to the declared route when no entry opens a desk page", async ({ page }) => {
		const route = await landing(page, {
			app_name: "frappe-like",
			app_route: "/desk/build",
			dock: [url_row],
		});

		expect(route).toBe("/desk/build");
	});

	test("treats an app declaring an /app route as a desk app", async ({ page }) => {
		const route = await landing(page, {
			app_name: "legacy-desk-app",
			app_route: "/app/legacy",
			dock: [sidebar_row("Email")],
		});

		expect(route).toBe(EMAIL_LANDING);
	});

	test("keeps an app outside the desk on its own route", async ({ page }) => {
		const route = await landing(page, {
			app_name: "crm",
			app_route: "/crm",
			desk_route: "/desk/frappe-crm",
			dock: [sidebar_row("Email")],
		});

		expect(route).toBe("/crm");
	});
});

test.describe("The header's Apps menu on a touch screen", () => {
	test.use({ hasTouch: true, isMobile: true, viewport: { width: 1180, height: 820 } });

	test("opens an app outside the desk on its own route", async ({ page, desk }) => {
		await open_desk(page, desk);
		await page.evaluate(() =>
			frappe.boot.app_data.push({
				app_name: "outside-app",
				app_title: "Outside App",
				app_route: "/me",
				on_apps_screen: 1,
			})
		);

		await page.locator(".sidebar-header").click();
		await page.getByRole("menuitem", { name: "Apps", exact: true }).click();
		await page.getByRole("menuitem", { name: "Outside App", exact: true }).click();

		await expect(page).toHaveURL((url) => url.pathname === "/me");
	});
});
