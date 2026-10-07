import { test, expect } from "../support";
import { TEST_USER } from "../support/config";

const PHONE = { width: 390, height: 844 };
const TODO_TAG = "mobile-scroll-test";
const TODO_COUNT = 45;

async function open_on_phone(page, desk, path) {
	await page.setViewportSize(PHONE);
	await page.goto(path);
	await desk.ready();
	await page.waitForFunction(() => document.body.classList.contains("has-mobile-nav"));
}

// replaces whatever filters the list saved last time, so each test starts from the seed
async function show_seeded_todos(page) {
	await page.evaluate(async (tag) => {
		await cur_list.filter_area.clear(false);
		await cur_list.filter_area.add([["ToDo", "description", "like", `${tag}%`]]);
	}, TODO_TAG);
}

test.describe("Phone tab bar", () => {
	// one seeded list for every test, rather than reseeding after each failure
	test.describe.configure({ mode: "serial" });

	const remove_todos = async (admin) => {
		const { message: todos } = await admin.call("frappe.client.get_list", {
			doctype: "ToDo",
			filters: [["description", "like", `${TODO_TAG}%`]],
			limit_page_length: 0,
		});
		for (const todo of todos) await admin.remove_doc("ToDo", todo.name);
	};

	test.beforeAll(async ({ admin }) => {
		await remove_todos(admin);
		for (let i = 0; i < TODO_COUNT; i++) {
			await admin.insert_doc("ToDo", {
				description: `${TODO_TAG} ${i}`,
				allocated_to: TEST_USER,
			});
		}
	});

	test.afterAll(async ({ admin }) => {
		await remove_todos(admin);
	});

	test("a single doctype has the tab bar, not a back button", async ({ page, desk }) => {
		await open_on_phone(page, desk, "/desk/system-settings");
		await expect(page.locator(".page-head .page-back-button")).toBeHidden();
		await expect(page.locator("frappe-mobile-nav")).toBeVisible();
	});

	test("a document form has a back button instead of the tab bar", async ({ page, desk }) => {
		await open_on_phone(page, desk, "/desk/todo");
		await page.evaluate(() => frappe.set_route("Form", "ToDo", "new-todo-1"));
		await expect(page.locator(".page-head .page-back-button:visible")).toHaveCount(1);
		await expect(page.locator("frappe-mobile-nav")).toBeHidden();
	});

	test("a list loads the next page as it scrolls", async ({ page, desk }) => {
		await open_on_phone(page, desk, "/desk/todo");
		await show_seeded_todos(page);
		await expect.poll(() => page.evaluate(() => cur_list.data.length)).toBe(20);
		await expect(page.locator(".frappe-list .list-paging-area")).toBeHidden();

		for (const expected of [40, TODO_COUNT]) {
			await page.locator(".frappe-list .list-end").scrollIntoViewIfNeeded();
			await expect.poll(() => page.evaluate(() => cur_list.data.length)).toBe(expected);
		}
		const names = await page.evaluate(() => cur_list.data.map((d) => d.name));
		expect(new Set(names).size).toBe(TODO_COUNT);
	});

	test("a filter change during a scroll load shows only the filtered rows", async ({
		page,
		desk,
	}) => {
		// hold every scroll load's response until the filter change has gone out and come back
		await page.route("**/api/method/frappe.desk.reportview.get", async (route) => {
			if (route.request().postDataJSON()?.start > 0) {
				await new Promise((resolve) => setTimeout(resolve, 2000));
			}
			await route.continue();
		});
		// the list end may be on screen as soon as the rows render, starting a load by itself
		const scroll_load = page.waitForRequest(
			(request) =>
				request.url().endsWith("/frappe.desk.reportview.get") &&
				request.postDataJSON()?.start > 0
		);
		await open_on_phone(page, desk, "/desk/todo");
		await show_seeded_todos(page);
		await expect.poll(() => page.evaluate(() => cur_list.data.length)).toBe(20);

		await page.evaluate(() => cur_list.loading_more || cur_list.load_more_on_scroll());
		await scroll_load;
		await page.evaluate((tag) => {
			cur_list.filter_area
				.clear(false)
				.then(() => cur_list.filter_area.add([["ToDo", "description", "=", `${tag} 7`]]));
		}, TODO_TAG);
		// let the held scroll load land after the filtered rows
		await page.waitForTimeout(3000);
		await expect
			.poll(() => page.evaluate(() => cur_list.data.map((d) => d.description)))
			.toEqual([`${TODO_TAG} 7`]);
	});

	test("picking a row in the navigation sheet routes without a reload", async ({
		page,
		desk,
	}) => {
		await open_on_phone(page, desk, "/desk/todo");
		await page.waitForFunction(() => frappe.ui.BottomSheet);
		await page.evaluate(() => (window.__no_reload = true));

		await page.locator(".page-head .navbar-breadcrumbs li:last-child").click();
		const sheet = page.locator(".es-bottom-sheet");
		await expect(sheet).toBeVisible();
		// browsing to another module first is what used to reload the page
		const other_module = sheet.locator(".desk-mobile-sheet-dock-item:not(.active)").first();
		if (await other_module.count()) await other_module.click();

		const row = sheet.locator(".standard-sidebar-item a.item-anchor[href^='/desk/']").first();
		const href = await row.getAttribute("href");
		await row.click();
		await expect(page).toHaveURL(new RegExp(href.replace(/\/$/, "")));
		expect(await page.evaluate(() => window.__no_reload)).toBe(true);
		await expect(sheet).toHaveCount(0);
	});

	test("the Desktop page header keeps only the logo and title", async ({ page, desk }) => {
		await open_on_phone(page, desk, "/desk");
		const header = page.locator(".desktop-navbar");
		await expect(header.locator("#brand-logo")).toBeVisible();
		await expect(header.locator(".desktop-navbar-title")).toHaveText("Desktop");
		await expect(header.locator(".search-widget-wrapper")).toBeHidden();
		await expect(header.locator(".desktop-notifications")).toBeHidden();
		await expect(header.locator(".desktop-avatar")).toBeHidden();
	});

	test("profile settings show when the language name lookup fails", async ({ page, admin }) => {
		// with no language set there is no lookup to fail
		await admin.set_value("User", TEST_USER, { language: "en" });
		const failed_lookup = page.waitForRequest(/frappe\.client\.get_value\?.*doctype=Language/);
		await page.route(/frappe\.client\.get_value\?.*doctype=Language/, (route) =>
			route.fulfill({ status: 500, contentType: "application/json", body: "{}" })
		);

		// not open_on_phone: desk.ready() waits on the standard page body, and an island
		// page draws into its own
		await page.setViewportSize(PHONE);
		await page.goto("/desk/profile/preferences");
		await failed_lookup;
		await expect(page.locator("button[role='switch']").first()).toBeVisible();
	});

	test("profile loads the name again on return, so a save keeps a change made elsewhere", async ({
		page,
		admin,
	}) => {
		const name_fields = ["middle_name", "last_name"];
		const { message: before } = await admin.call("frappe.client.get_value", {
			doctype: "User",
			filters: TEST_USER,
			fieldname: name_fields,
		});
		const field = (label) => page.getByLabel(label);

		try {
			await page.setViewportSize(PHONE);
			await page.goto("/desk/profile/personal");
			await expect(field("First Name")).not.toHaveValue("");

			// desk keeps Profile mounted while another page changes the name
			await page.evaluate(() => frappe.set_route("List", "ToDo"));
			await expect(page).toHaveURL(/\/todo/);
			await page.evaluate(() =>
				frappe.xcall("frappe.client.set_value", {
					doctype: "User",
					name: frappe.session.user,
					fieldname: "last_name",
					value: "Changed Elsewhere",
				})
			);

			await page.evaluate(() => frappe.set_route("profile", "personal"));
			await expect(field("Last Name")).toHaveValue("Changed Elsewhere");
			await field("Middle Name").fill("Middle");
			const saved = page.waitForResponse((r) => r.url().includes("frappe.client.set_value"));
			await page.getByRole("button", { name: "Save", exact: true }).click();
			await saved;

			const { message: after } = await admin.call("frappe.client.get_value", {
				doctype: "User",
				filters: TEST_USER,
				fieldname: name_fields,
			});
			expect(after).toEqual({ middle_name: "Middle", last_name: "Changed Elsewhere" });
		} finally {
			await admin.set_value("User", TEST_USER, {
				middle_name: before.middle_name || "",
				last_name: before.last_name || "",
			});
		}
	});

	test("the phone pages send a wide screen to their desktop home", async ({ page, desk }) => {
		await page.goto("/desk/notifications");
		await desk.ready();
		await expect(page).toHaveURL(/\/notification-log/);

		await page.goto("/desk/profile");
		await desk.ready();
		await expect(page).toHaveURL(/\/user\//);

		// desk keeps the page's island mounted, so a second visit has to redirect as well
		await page.evaluate(() => frappe.set_route("List", "ToDo"));
		await expect(page).toHaveURL(/\/todo/);
		await page.evaluate(() => frappe.set_route("profile"));
		await expect(page).toHaveURL(/\/user\//);
	});
});
