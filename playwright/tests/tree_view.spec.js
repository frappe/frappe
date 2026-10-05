import { test, expect } from "../support";

const TREE_URL = "/app/custom-tree/view/tree";

const tree_link = (page, label) => page.locator(`.tree-link[data-label="${label}"]`);
const tree_page = (page) => page.locator('[data-page-route="Tree/Custom Tree"]');
const menu_item = (page, label) =>
	page.locator('[role="menu"] .es-menu__item', { hasText: label }).first();

test.describe("Tree View", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.setup_tree_doctype");
	});

	test("keeps expanded nodes when navigating back to the tree", async ({ page }) => {
		await page.goto(TREE_URL);

		await tree_link(page, "Parent Node").click();
		await expect(tree_link(page, "Child Node")).toBeVisible();

		await page.evaluate(() => frappe.set_route("List", "ToDo"));
		await expect(tree_page(page)).toBeHidden();

		await page.goBack();
		await expect(tree_page(page)).toBeVisible();
		await expect(tree_link(page, "Child Node")).toBeVisible();

		expect(await page.evaluate(() => cur_tree.nodes["Parent Node"].expanded)).toBe(true);
	});

	test("shows Expand All / Collapse All only when the tree's state warrants it", async ({
		page,
	}) => {
		await page.goto(TREE_URL);

		const toggle_menu = () =>
			page
				.locator(".tree-toolbar-actions .es-button", { hasText: "Expand/Collapse" })
				.click();
		const assert_buttons = async (expand_enabled, collapse_enabled) => {
			await toggle_menu();
			await expect(menu_item(page, "Expand All")).toBeEnabled({ enabled: expand_enabled });
			await expect(menu_item(page, "Collapse All")).toBeEnabled({
				enabled: collapse_enabled,
			});
			await toggle_menu();
		};
		const click_toolbar_button = async (label) => {
			await toggle_menu();
			await menu_item(page, label).click();
		};

		// wait for the root's children to render before opening the menu — the
		// expansion state is only meaningful once the tree has actually loaded
		await expect(tree_link(page, "Parent Node")).toBeVisible();

		await assert_buttons(true, false);

		await tree_link(page, "Parent Node").click();
		await expect(tree_link(page, "Child Node")).toBeVisible();
		await assert_buttons(true, true);

		await click_toolbar_button("Expand All");
		await expect(tree_link(page, "Child Node")).toBeVisible();
		await assert_buttons(false, true);

		await tree_link(page, "All Trees").click();
		await expect(tree_link(page, "Parent Node")).toBeHidden();
		await assert_buttons(true, false);

		await tree_link(page, "All Trees").click();
		await expect(tree_link(page, "Child Node")).toBeVisible();
		await assert_buttons(false, true);

		await click_toolbar_button("Collapse All");
		await expect(tree_link(page, "Child Node")).toHaveCount(0);
		await assert_buttons(true, false);
	});

	test("sorts nodes by name and remembers the choice", async ({ page }) => {
		await page.goto(TREE_URL);

		const sort_button = page.locator(".tree-toolbar-actions .es-button").first();
		const root_labels = () =>
			page.evaluate(() =>
				cur_tree.root_node.$ul
					.children("li.tree-node")
					.map((i, li) => $(li).children(".tree-link").attr("data-label"))
					.get()
			);
		const pick = async (label) => {
			await sort_button.click();
			await menu_item(page, label).click();
			await expect(sort_button).toContainText(label);
		};

		await expect(tree_link(page, "Parent Node")).toBeVisible();

		await pick("Name Z to A");
		expect((await root_labels())[0]).toBe("Second Parent Node");

		await pick("Name A to Z");
		let labels = await root_labels();
		expect(labels[0]).toBe("Parent Node");
		// natural order: 2 before 10
		expect(labels.indexOf("Scroll Node 2")).toBeLessThan(labels.indexOf("Scroll Node 10"));

		await page.reload();
		await expect(tree_link(page, "Parent Node")).toBeVisible();
		await expect(sort_button).toContainText("Name A to Z");
		labels = await root_labels();
		expect(labels.indexOf("Scroll Node 2")).toBeLessThan(labels.indexOf("Scroll Node 10"));

		await pick("Default Order");
		labels = await root_labels();
		// server order is by name
		expect(labels.indexOf("Scroll Node 10")).toBeLessThan(labels.indexOf("Scroll Node 2"));
	});

	test("restores the scroll position when navigating back to the tree", async ({ page }) => {
		await page.goto(TREE_URL);

		const scroll_top = () =>
			page
				.locator(".main-section")
				.first()
				.evaluate((el) => el.scrollTop);

		await tree_link(page, "Scroll Node 39").scrollIntoViewIfNeeded();
		await expect.poll(scroll_top).toBeGreaterThan(0);
		const scroll_position = await scroll_top();

		await page.evaluate(() => frappe.set_route("List", "ToDo"));
		await expect(tree_page(page)).toBeHidden();

		await page.goBack();
		await expect(tree_page(page)).toBeVisible();
		await expect.poll(scroll_top).toBe(scroll_position);
	});
});
