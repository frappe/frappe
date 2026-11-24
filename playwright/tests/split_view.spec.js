import { test, expect } from "../support";
import { TEST_USER } from "../support/config";

const PROPERTY_SETTER = "ToDo-main-allow_split_view";
const ROWS = ".split-view .es-list__row";

const like_filter = (stamp) => encodeURIComponent(JSON.stringify(["like", `%${stamp}%`]));

test.describe("Split View", () => {
	const stamp = `split-view-${Date.now()}`;
	const todos = [];

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc(
			"Property Setter",
			{
				doc_type: "ToDo",
				doctype_or_field: "DocType",
				property: "allow_split_view",
				property_type: "Check",
				value: "1",
			},
			true
		);
		for (const label of ["one", "two", "three"]) {
			todos.push(
				await admin.insert_doc("ToDo", {
					description: `${stamp} ${label}`,
					allocated_to: TEST_USER,
				})
			);
		}
	});

	test.afterAll(async ({ admin }) => {
		for (const todo of todos) {
			await admin.remove_doc("ToDo", todo.name, true);
		}
		await admin.remove_doc("Property Setter", PROPERTY_SETTER, true);
	});

	const selected_row = (page) => page.locator(`${ROWS}[data-selected]`);
	const detail_title = (page) => page.locator(".split-view-preview-title");
	// the skeleton draws placeholder labels in the same list
	const detail_fields = (page) =>
		page.locator(".split-view-preview-body .split-view-fields dt:not(:has(.es-skeleton))");
	const view_menu = async (page) => {
		await page.locator(".custom-btn-group.view-switcher button").click();
		return page.locator(".es-menu[data-state='open']");
	};

	async function open_split_view(page) {
		await page.goto(`/desk/todo/view/split?description=${like_filter(stamp)}`);
		await expect(page.locator(ROWS)).toHaveCount(3);
		// the list's own order, newest first by default
		return page.evaluate(() => cur_list.data.map((doc) => doc.name));
	}

	test("opens the clicked record beside the list and puts it in the URL", async ({ page }) => {
		const names = await open_split_view(page);
		await expect(page.locator(".split-view-empty")).toContainText("No ToDo selected");

		await page.locator(ROWS).first().click();
		await expect(page).toHaveURL(new RegExp(`/view/split/${names[0]}\\?description=`));
		await expect(selected_row(page)).toHaveAttribute("data-id", names[0]);
		await expect(detail_title(page)).toContainText(stamp);
		await expect(detail_fields(page)).not.toHaveCount(0);
	});

	test("a link to the same split view with other filters shows their rows", async ({ page }) => {
		const names = await open_split_view(page);
		await page.locator(ROWS).first().click();
		await expect(page).toHaveURL(new RegExp(`/view/split/${names[0]}`));
		const two = todos.find((todo) => todo.description.endsWith(" two")).name;

		await page.evaluate((stamp) => {
			frappe.route_options = { description: JSON.stringify(["like", `%${stamp} two%`]) };
			frappe.set_route("List", "ToDo", "Split");
		}, stamp);
		await expect(page.locator(ROWS)).toHaveCount(1);
		await expect(page.locator(ROWS).first()).toHaveAttribute("data-id", two);
	});

	test("moves the selection with j and k, and Escape clears it", async ({ page }) => {
		const names = await open_split_view(page);
		await page.locator(ROWS).first().click();
		await expect(page).toHaveURL(new RegExp(`/view/split/${names[0]}`));
		// keys go to the page, not to the focused row
		await page.locator(".split-view-detail").click({ position: { x: 5, y: 5 } });

		await page.keyboard.press("j");
		await expect(page).toHaveURL(new RegExp(`/view/split/${names[1]}`));
		await expect(selected_row(page)).toHaveAttribute("data-id", names[1]);

		await page.keyboard.press("j");
		await expect(page).toHaveURL(new RegExp(`/view/split/${names[2]}`));

		await page.keyboard.press("k");
		await expect(page).toHaveURL(new RegExp(`/view/split/${names[1]}`));
		await expect(detail_title(page)).toContainText(stamp);

		await page.keyboard.press("Escape");
		await expect(page).toHaveURL(/\/view\/split\?description=/);
		await expect(selected_row(page)).toHaveCount(0);
		await expect(page.locator(".split-view-empty")).toContainText("3 records match");
	});

	test("shows a skeleton only for a slow load, and a record seen before at once", async ({
		page,
	}) => {
		const names = await open_split_view(page);
		const skeleton = page.locator(".split-view-preview-body .es-skeleton");
		const fields = detail_fields(page);
		let delay = 1500;
		await page.route("**/api/method/frappe.desk.doc_preview.get_preview*", async (route) => {
			await new Promise((resolve) => setTimeout(resolve, delay));
			await route.continue();
		});

		await page.locator(ROWS).first().click();
		// the header shows at once, the body stays empty until the skeleton's delay passes
		await expect(detail_title(page)).toContainText(stamp);
		await expect(skeleton).toHaveCount(0);
		await expect(skeleton).not.toHaveCount(0);
		await expect(fields).not.toHaveCount(0, { timeout: 5000 });

		await page.locator(ROWS).nth(2).click();
		await expect(fields).not.toHaveCount(0, { timeout: 5000 });
		// back to the first: drawn from memory, no skeleton and no wait for the slow server
		await page.locator(ROWS).first().click();
		await expect(page).toHaveURL(new RegExp(`/view/split/${names[0]}`));
		await expect(fields).not.toHaveCount(0, { timeout: 200 });
		await expect(skeleton).toHaveCount(0);
	});

	test("Back leaves the page instead of stepping through records", async ({ page }) => {
		await page.goto("/desk/todo");
		const names = await open_split_view(page);
		for (const name of names) {
			await page.locator(`${ROWS}[data-id="${name}"]`).click();
			await expect(page).toHaveURL(new RegExp(`/view/split/${name}`));
		}
		await page.goBack();
		await expect(page).not.toHaveURL(/\/view\/split/);
	});

	test("sends a DocType that did not opt in to its list", async ({ page }) => {
		await page.goto("/desk/note/view/split");
		await expect(page).toHaveURL(/\/note\/view\/list/);
		await expect(page.locator(".split-view")).toHaveCount(0);
	});

	test("offers Split in the view switcher only for a DocType that opted in", async ({
		page,
	}) => {
		await page.goto("/desk/todo/view/list");
		await expect(await view_menu(page)).toContainText("Split View");
		await page.keyboard.press("Escape");

		await page.goto("/desk/note/view/list");
		const menu = await view_menu(page);
		await expect(menu).toContainText("Report View");
		await expect(menu).not.toContainText("Split View");
	});

	test("folds the sidebar while the split view shows and brings it back after", async ({
		page,
	}) => {
		const body = page.locator("body");
		await page.goto("/desk/todo/view/list");
		await page.evaluate(() => frappe.app.sidebar.open());
		await expect(body).not.toHaveClass(/(^|\s)sidebar-collapsed(\s|$)/);

		await page.evaluate(() => frappe.set_route("List", "ToDo", "Split"));
		await expect(page.locator(".split-view")).toBeVisible();
		await expect(body).toHaveClass(/(^|\s)sidebar-collapsed(\s|$)/);

		await page.evaluate(() => frappe.set_route("List", "ToDo", "List"));
		await expect(page).toHaveURL(/\/todo\/view\/list/);
		await expect(body).not.toHaveClass(/(^|\s)sidebar-collapsed(\s|$)/);
	});

	test("draws a DocType's own detail with render_detail", async ({ page }) => {
		await page.goto("/desk/todo/view/list");
		// todo_list.js replaces the ToDo settings when the list loads, so set them after it
		await page.waitForFunction(() => window.cur_list?.doctype === "ToDo");
		await page.evaluate((stamp) => {
			window.destroyed_details = [];
			(frappe.listview_settings.ToDo ||= {}).split_view = {
				render_detail: ({ name, $wrapper }) => {
					$("<p class='test-split-detail'></p>").text(name).appendTo($wrapper);
					return { destroy: () => window.destroyed_details.push(name) };
				},
			};
			frappe.route_options = { description: JSON.stringify(["like", `%${stamp}%`]) };
			frappe.set_route("List", "ToDo", "Split");
		}, stamp);
		await expect(page.locator(ROWS)).toHaveCount(3);
		const names = await page.evaluate(() => cur_list.data.map((doc) => doc.name));
		const detail = page.locator(".split-view-custom-detail .test-split-detail");

		await page.locator(ROWS).first().click();
		await expect(detail).toHaveText(names[0]);
		await expect(page.locator(".split-view-preview")).toHaveCount(0);

		await page.locator(ROWS).nth(1).click();
		await expect(detail).toHaveText(names[1]);
		expect(await page.evaluate(() => window.destroyed_details)).toEqual([names[0]]);
	});

	test.describe("with more rows than a page", () => {
		const paging_stamp = `split-view-paging-${Date.now()}`;
		const paged_todos = [];
		const PAGE_LENGTH = 25;
		const TOTAL = 30;

		test.use({ viewport: { width: 1280, height: 600 } });

		test.beforeAll(async ({ admin }) => {
			for (let i = 0; i < TOTAL; i++) {
				paged_todos.push(
					await admin.insert_doc("ToDo", {
						description: `${paging_stamp} ${i}`,
						allocated_to: TEST_USER,
					})
				);
			}
		});

		test.afterAll(async ({ admin }) => {
			for (const todo of paged_todos) {
				await admin.remove_doc("ToDo", todo.name, true);
			}
		});

		async function open_first_page(page) {
			await page.goto(`/desk/todo/view/split?description=${like_filter(paging_stamp)}`);
			await expect(page.locator(ROWS).first()).toBeVisible();
			await page.evaluate((page_length) => {
				cur_list.start = 0;
				cur_list.page_length = cur_list.selected_page_count = page_length;
				return cur_list.refresh();
			}, PAGE_LENGTH);
			await expect(page.locator(ROWS)).toHaveCount(PAGE_LENGTH);
		}

		test("loads the next page when the rows scroll to their end", async ({ page }) => {
			await open_first_page(page);
			await page
				.locator(".split-view-rows")
				.evaluate((rows) => (rows.scrollTop = rows.scrollHeight));
			await expect(page.locator(ROWS)).toHaveCount(TOTAL);
		});

		test("j on the last loaded row loads the next page and opens its first row", async ({
			page,
		}) => {
			await open_first_page(page);
			// only the key may load the next page
			await page.evaluate(() => cur_list.pane.more_observer.disconnect());
			const last = await page.evaluate(() => cur_list.data.at(-1).name);

			await page
				.locator(ROWS)
				.nth(PAGE_LENGTH - 1)
				.click();
			await expect(page).toHaveURL(new RegExp(`/view/split/${last}`));
			await expect(page.locator(".split-view-position")).toHaveText(
				`${PAGE_LENGTH} of ${TOTAL}`
			);
			await page.locator(".split-view-detail").click({ position: { x: 5, y: 5 } });

			await page.keyboard.press("j");
			await expect(page.locator(ROWS)).toHaveCount(TOTAL);
			const next = await page.evaluate((index) => cur_list.data[index].name, PAGE_LENGTH);
			await expect(page).toHaveURL(new RegExp(`/view/split/${next}`));
			await expect(selected_row(page)).toHaveAttribute("data-id", next);
		});
	});
});
