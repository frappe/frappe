import { test, expect } from "../support";

// The Link field with the combobox setting on, driven through its panel.
test.describe("Control Link (combobox)", () => {
	let todo;
	let todo_stamp;

	test.beforeAll(async ({ admin }) => {
		await admin.set_value("System Settings", "System Settings", {
			enable_combobox_link_field: 1,
		});
	});

	test.afterAll(async ({ admin }) => {
		await admin.set_value("System Settings", "System Settings", {
			enable_combobox_link_field: 0,
		});
	});

	// a fresh ToDo per test, found by its stamp: other specs leave ToDos with the same words
	test.beforeEach(async ({ page, desk, api }) => {
		todo_stamp = String(Date.now());
		[todo] = await api.create_records({
			doctype: "ToDo",
			description: `this is a test todo for link ${todo_stamp}`,
		});
		await page.goto("/desk/website");
		await desk.ready();
	});

	test.afterEach(async ({ admin }) => {
		await admin.remove_doc("ToDo", todo, true);
	});

	const panel = (page) => page.locator(".es-combobox__panel[data-state='open']");
	const search = (page) => panel(page).locator(".es-combobox__input");
	const rows = (page) => panel(page).locator(".es-combobox__list [role='option']");
	const value_of = (dialog, fieldname) => dialog.evaluate((d, f) => d.get_value(f), fieldname);
	const link_dialog = (desk, fieldname, options) =>
		desk.dialog({
			title: "Link",
			fields: [{ label: options, fieldname, fieldtype: "Link", options }],
		});

	test("picks a row, clears it, and is driven from the keyboard", async ({ page, desk }) => {
		const dialog = await link_dialog(desk, "link", "ToDo");
		const field = page.locator(".modal.show .frappe-control[data-fieldname=link] input");

		// the first field of a dialog opens with its search focused; Enter picks the match
		await expect(search(page)).toBeFocused();
		await search(page).pressSequentially(todo_stamp, { delay: 50 });
		await expect(rows(page)).toHaveCount(1);
		await search(page).press("Enter");
		await expect(panel(page)).toHaveCount(0);
		await expect.poll(() => value_of(dialog, "link")).toBe(todo);

		// Backspace clears and opens the panel; Escape settles the clear
		await field.press("Backspace");
		await expect(panel(page)).toBeVisible();
		await search(page).press("Escape");
		await expect(panel(page)).toHaveCount(0);
		await expect.poll(() => value_of(dialog, "link")).toBe("");
		await expect(field).toBeFocused();

		// ArrowDown opens it, moves through the rows, and Tab picks the row moved to
		await field.press("ArrowDown");
		await expect(search(page)).toBeFocused();
		await expect(rows(page).nth(1)).toBeVisible();
		await search(page).press("ArrowDown");
		const moved_to = await page.evaluate(
			() => cur_dialog.get_field("link").combobox.highlighted.option.value
		);
		await search(page).press("Tab");
		await expect(panel(page)).toHaveCount(0);
		await expect.poll(() => value_of(dialog, "link")).toBe(moved_to);
	});

	test("Select mode lists everything without a search box and jumps by letter", async ({
		page,
		desk,
	}) => {
		await page.evaluate(() => {
			frappe.boot.link_settings = {
				...(frappe.boot.link_settings || {}),
				Role: { display_mode: "Select" },
			};
		});
		const dialog = await link_dialog(desk, "role", "Role");

		await expect(rows(page).first()).toBeVisible();
		await expect(search(page)).toHaveCount(0);
		await page.keyboard.type("sys");
		await expect(panel(page).locator("[role='option'][data-highlighted]")).toContainText(
			"System Manager"
		);
		await page.keyboard.press("Tab");
		await expect(panel(page)).toHaveCount(0);
		await expect.poll(() => value_of(dialog, "role")).toBe("System Manager");
	});

	test("pages a long list on scroll, and map_options groups the rows", async ({
		page,
		desk,
	}) => {
		const dialog = await link_dialog(desk, "dt", "DocType");
		const list = panel(page).locator(".es-combobox__list");
		const scroll_down = () => list.evaluate((el) => (el.scrollTop = el.scrollHeight));

		// a page at a time, the next one fetched on scroll
		await expect(rows(page)).toHaveCount(10);
		await scroll_down();
		await expect.poll(() => rows(page).count()).toBeGreaterThan(10);
		await search(page).press("Escape");
		await expect(panel(page)).toHaveCount(0);

		// every page returns both groups: later rows join the group with that label
		await dialog.evaluate((d) => {
			d.get_field("dt").map_options = (rows) => [
				{ group: "Recently used", options: [rows[0]] },
				{ group: "All", options: rows },
			];
		});
		await page.locator(".modal.show .frappe-control[data-fieldname=dt] .es-combobox").click();
		const labels = panel(page).locator(".es-menu__group-label");
		await expect(labels).toHaveCount(2);
		await expect(labels.first()).toContainText("Recently used");
		await scroll_down();
		await expect.poll(() => rows(page).count()).toBeGreaterThan(11);
		await expect(labels).toHaveCount(2);
	});
});
