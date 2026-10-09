import { test, expect } from "../support";

const CHECK_ALL = ".list-header-subject .list-subject .list-check-all";

test.describe("List View", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.setup_workflow");
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("Workflow", "Test ToDo", true);
	});

	test("Keep checkbox checked after Refresh", async ({ page, desk }) => {
		await desk.go_to_list("ToDo");
		await desk.clear_filters();
		await page.locator(CHECK_ALL).click();
		await page.locator("button[data-original-title='Reload List']").click();
		await expect(
			page.locator(".list-row-container .list-row-checkbox:checked").first()
		).toBeVisible();
	});

	test("keeps a Check '= No' standard filter applied", async ({ page, desk }) => {
		await desk.go_to_list("Web Page");
		await desk.clear_filters();
		await page.evaluate(() => {
			frappe.route_options = { published: ["=", 0] };
			frappe.set_route("List", "Web Page");
		});
		await expect(page.locator(".filter-selector .filter-button .button-label")).toContainText(
			"Filters"
		);
		await expect
			.poll(() =>
				page.evaluate(() =>
					cur_list.filter_area
						.get()
						.some((f) => f[1] === "published" && String(f[3]) === "0")
				)
			)
			.toBe(true);
	});

	test('enables "Actions" button', async ({ page, desk }) => {
		const actions = [
			"Approve",
			"Reject",
			"Copy to Clipboard",
			"Export",
			"Assign To",
			"Clear Assignment",
			"Apply Assignment Rule",
			"Add Tags",
			"Print",
		];
		await desk.go_to_list("ToDo");
		await desk.clear_filters();
		const common_actions = page.waitForResponse(
			(res) =>
				res.request().method() === "POST" &&
				res
					.url()
					.includes("/api/method/frappe.model.workflow.get_common_transition_actions")
		);
		await page.locator(CHECK_ALL).click();
		// selecting rows triggers the workflow-actions refresh (debounced);
		// wait for it to hide "Review" (not common to the selected docs)
		// before opening — the menu snapshots its items at open
		await common_actions;
		await expect(
			page
				.locator('.actions-btn-group [data-label="Review"]')
				.locator("xpath=ancestor::li[1]")
		).toHaveCSS("display", "none");
		await page.getByRole("button", { name: "Actions", exact: true }).click();

		const menu_items = page.locator('.es-menu [role="menuitem"]');
		await expect(menu_items).toHaveCount(9);
		for (const [index, action] of actions.entries()) {
			await expect(menu_items.nth(index)).toContainText(action);
		}

		const bulk_approval = page.waitForResponse(
			(res) =>
				res.request().method() === "POST" &&
				res.url().includes("api/method/frappe.model.workflow.bulk_workflow_approval")
		);
		await menu_items.filter({ hasText: "Approve" }).first().click();
		await bulk_approval;
		await desk.hide_dialog();
		await page.reload();
		await desk.clear_filters();
		await expect(
			page.locator(".list-row-container:visible", { hasText: "Approved" }).first()
		).toBeVisible();
	});

	test("Adds a button to each list view row", async ({ page, desk, api }) => {
		const r = await api.call("frappe.client.get_value", {
			doctype: "ToDo",
			filters: {
				reference_name: ["is", "set"],
			},
			fieldname: "name",
		});
		const todo_name = r.message.name;
		await desk.go_to_list("ToDo");

		const open_button = page.locator(`.btn-default[data-name="${todo_name}"]`);
		await open_button.scrollIntoViewIfNeeded();
		await expect(open_button).toBeVisible();
		await open_button.click();

		await expect.poll(() => page.evaluate(() => window.cur_frm?.doc.doctype)).toBe("ToDo");
		expect(await page.evaluate(() => cur_frm.doc.name)).not.toBe(todo_name);
	});

	test("translates field labels in the bulk edit dialog", async ({ page, desk, api }) => {
		const translations = {
			Route: "Routen-Pfad",
			"Web Page": "Webseite",
			"CSS Class": "CSS-Klasse",
			"Page Building Blocks": "Seitenbausteine",
		};

		await api.insert_doc(
			"Web Page",
			{ title: "Impressum", route: "impressum", content_type: "Rich Text" },
			true
		);
		await desk.go_to_list("Web Page");
		await desk.clear_filters();
		await page.locator(CHECK_ALL).click();

		await page.evaluate(
			(translations) => Object.assign(frappe._messages, translations),
			translations
		);
		await desk.click_action_button("Edit");

		const field = desk.get_open_dialog().locator('input[data-fieldname="field"]');
		const suggestions = page.locator(".awesomplete li:visible");

		await field.clear();
		await field.pressSequentially("Routen-Pfad");
		await expect(
			suggestions.filter({ hasText: "Routen-Pfad (Webseite)" }).first()
		).toBeVisible();

		await field.clear();
		await field.pressSequentially("CSS-Klasse");
		await expect(
			suggestions.filter({ hasText: "CSS-Klasse (Seitenbausteine)" }).first()
		).toBeVisible();

		await desk.hide_dialog();
		await api.remove_doc("Web Page", "impressum");
	});

	test("keeps selected rows checked after a list rerender", async ({ page, desk }) => {
		await desk.go_to_list("ToDo");
		await desk.clear_filters();

		await page.locator(".list-row-checkbox").first().click();

		const selected_docnames = await page.evaluate(() => Array.from(cur_list.checked_docnames));
		expect(selected_docnames.length).toBe(1);

		const selected_docname = selected_docnames[0];
		await page.evaluate(() => cur_list.render_list());

		await expect
			.poll(() =>
				page.evaluate((docname) => {
					const $checkbox = cur_list.find_checkbox_by_docname(docname);
					return { length: $checkbox.length, checked: $checkbox.prop("checked") };
				}, selected_docname)
			)
			.toEqual({ length: 1, checked: true });
	});

	test("preserves select-all across virtualized window rerenders", async ({ page, desk }) => {
		await desk.go_to_list("ToDo");
		await desk.clear_filters();

		const data_length = await page.evaluate(() => {
			cur_list.virtualization_threshold = 1;
			cur_list.render_list();
			return cur_list.data.length;
		});
		expect(data_length).toBeGreaterThan(0);

		await expect(
			page.locator('.list-row-container[data-virtual-row="1"]').first()
		).toBeAttached();
		await page.locator(CHECK_ALL).click();

		const all_checked = () =>
			page.evaluate(() => cur_list.checked_docnames.size === cur_list.data.length);
		expect(await all_checked()).toBe(true);

		await page.locator(".result-container").evaluate((el) => el.scrollTo(0, el.scrollHeight));
		await page.evaluate(() => cur_list.render_virtual_rows(true));

		expect(await all_checked()).toBe(true);

		await expect(
			page.locator(".result-container .list-row-checkbox:checked").first()
		).toBeAttached();
	});

	test("keeps mobile virtual rows rendered during fast downward scroll", async ({
		page,
		desk,
	}) => {
		await page.setViewportSize({ width: 375, height: 667 });
		await desk.go_to_list("ToDo");
		await desk.clear_filters();

		const data_length = await page.evaluate(() => {
			cur_list.virtualization_threshold = 1;
			cur_list.render_list();
			return cur_list.data.length;
		});
		expect(data_length).toBeGreaterThan(0);

		await expect(
			page.locator('.list-row-container[data-virtual-row="1"]').first()
		).toBeAttached();

		await page.locator(".result-container").evaluate((el) => el.scrollTo(0, el.scrollHeight));
		await page.evaluate(() => cur_list.render_virtual_rows(true));

		await expect(
			page.locator('.list-row-container[data-virtual-row="1"] .list-row')
		).not.toHaveCount(0);

		const state = await page.evaluate(() => ({
			start: cur_list.virtualization_state.start,
			end: cur_list.virtualization_state.end,
		}));
		expect(state.end).toBeGreaterThan(state.start);
	});

	test("flips sort order icon and title", async ({ page, desk }) => {
		await desk.go_to_list("ToDo");
		await desk.clear_filters();

		await page.evaluate(() => {
			const sort_selector = cur_list.sort_selector;
			sort_selector.set_value(sort_selector.sort_by, "desc");
		});

		const order = page.locator(".sort-selector .btn-order");
		await expect(order).toHaveAttribute("title", "descending");
		await expect(order.locator(".sort-order use")).toHaveAttribute(
			"href",
			"#icon-arrow-down-wide-narrow"
		);

		await order.click();
		await expect(order).toHaveAttribute("data-value", "asc");
		await expect(order).toHaveAttribute("title", "ascending");
		await expect(order.locator(".sort-order use")).toHaveAttribute(
			"href",
			"#icon-arrow-up-narrow-wide"
		);
	});

	test("opens an empty filter row with all fields listed", async ({ page, desk }) => {
		await desk.go_to_list("ToDo");
		await desk.clear_filters();
		await desk.open_list_filter();

		const area = page.locator(".filter-popover .fieldname-select-area").first();
		const input = area.locator("input");
		const highlighted = area.locator('li[aria-selected="true"]');

		await expect(input).toBeFocused();
		await expect(input).toHaveValue("");
		await expect(area.locator("li", { hasText: /^Status$/ })).toBeVisible();
		await expect(highlighted).toHaveCount(0);

		await input.pressSequentially("Status");
		await input.press("Enter");
		await input.blur();
		await expect(input).toHaveValue("Status");

		// blur without a selection restores the current field
		await input.click();
		await input.pressSequentially("Desc");
		await input.blur();
		await expect(input).toHaveValue("Status");

		// Tab on the full list keeps the current field instead of the first one
		await input.click();
		await expect(input).toHaveValue("");
		await expect(highlighted).toHaveText("Status");
		await input.press("Tab");
		await expect(input).toHaveValue("Status");
		expect(
			await page.evaluate(() =>
				cur_list.filter_area.filter_list.filters[0].fieldselect.get_value()
			)
		).toBe("ToDo.status");
	});

	test("does not focus saved filters when the popover opens", async ({ page, desk }) => {
		await desk.go_to_list("ToDo");
		await desk.clear_filters();
		await page.evaluate(() =>
			cur_list.filter_area.add([["ToDo", "owner", "like", "%example.com%"]])
		);
		await desk.open_list_filter();

		const input = page.locator(".filter-popover .fieldname-select-area input").first();
		await expect(input).toHaveValue("Created By");
		await expect(input).not.toBeFocused();
		await expect(page.locator(".filter-popover")).toBeFocused();

		// keyboard users reach the first field with Tab and keep the whole filter with another Tab
		await page.keyboard.press("Tab");
		await expect(input).toBeFocused();
		await page.keyboard.press("Tab");
		await expect(input).toHaveValue("Created By");
		expect(
			await page.evaluate(() => cur_list.filter_area.filter_list.filters[0].get_value())
		).toEqual(["ToDo", "owner", "like", "%example.com%"]);

		// Escape outside a field closes the popover and returns focus to the button
		await page.locator(".filter-popover .remove-filter[role=button]").first().focus();
		await page.keyboard.press("Escape");
		await expect(page.locator(".filter-popover")).toBeHidden();
		await expect(page.locator(".filter-section .filter-button")).toBeFocused();
	});
});
