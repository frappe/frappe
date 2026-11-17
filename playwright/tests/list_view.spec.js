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

	test('enables "Actions" button', async ({ page, desk }) => {
		const actions = [
			"Approve",
			"Reject",
			"Export",
			"Assign To",
			"Clear Assignment",
			"Apply Assignment Rule",
			"Add Tags",
			"Print",
		];
		await desk.go_to_list("ToDo");
		await desk.clear_filters();
		await page.locator(CHECK_ALL).click();
		await page.getByRole("button", { name: "Actions", exact: true }).click();

		const menu_items = page.locator(".dropdown-menu li:visible .dropdown-item");
		await expect(menu_items).toHaveCount(8);
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

	test("keeps the selection after a bulk edit", async ({ page, desk, api }) => {
		const suffix = Date.now().toString(36);
		const selected = [];
		for (const route of [`bulk-edit-a-${suffix}`, `bulk-edit-b-${suffix}`]) {
			const doc = await api.insert_doc("Web Page", {
				title: route,
				route,
				content_type: "Rich Text",
			});
			selected.push(doc.name);
		}

		try {
			await desk.go_to_list("Web Page");
			await desk.clear_filters();
			for (const name of selected) {
				await page.locator(`.list-row-checkbox[data-name="${name}"]`).click();
			}

			await desk.click_action_button("Edit");
			await page.waitForFunction(() => cur_dialog?.display);
			await page.evaluate(async () => {
				await cur_dialog.set_value("field", "Text Align");
				await cur_dialog.set_value("value", "Center");
			});
			await desk.click_modal_primary_button("Update 2 records");
			await expect(page.locator(".modal:visible")).toHaveCount(0);

			await expect
				.poll(() => page.evaluate(() => cur_list.get_checked_items(true).sort()))
				.toEqual(selected.sort());
			await expect(page.locator(".list-row-checkbox:checked")).toHaveCount(2);
		} finally {
			for (const name of selected) {
				await api.remove_doc("Web Page", name);
			}
		}
	});

	test("clears the selection when a bulk action is queued", async ({ page, desk, api }) => {
		// More than 5 docs makes bulk_apply enqueue instead of running inline.
		const selected = [];
		for (let i = 0; i < 6; i++) {
			const doc = await api.insert_doc("ToDo", { description: `queued bulk ${i}` });
			selected.push(doc.name);
		}

		try {
			await desk.go_to_list("ToDo");
			await desk.clear_filters();
			for (const name of selected) {
				await page.locator(`.list-row-checkbox[data-name="${name}"]`).click();
			}

			await desk.click_action_button("Apply Assignment Rule");

			await expect
				.poll(() => page.evaluate(() => cur_list.get_checked_items(true).length))
				.toBe(0);
			await expect(page.locator(".list-row-checkbox:checked")).toHaveCount(0);
		} finally {
			for (const name of selected) {
				await api.remove_doc("ToDo", name);
			}
		}
	});

	test("clears a partial selection from the header checkbox", async ({ page, desk, api }) => {
		const todos = [];
		for (let i = 0; i < 2; i++) {
			const doc = await api.insert_doc("ToDo", { description: `partial selection ${i}` });
			todos.push(doc.name);
		}

		try {
			await desk.go_to_list("ToDo");
			await desk.clear_filters();

			await page.locator(`.list-row-checkbox[data-name="${todos[0]}"]`).click();
			const header_check = page.locator(".checkbox-actions .list-check-all");
			await expect.poll(() => header_check.evaluate((el) => el.indeterminate)).toBe(true);

			await header_check.click();
			await expect
				.poll(() => page.evaluate(() => cur_list.get_checked_items(true).length))
				.toBe(0);
			await expect(page.locator(".list-row-checkbox:checked")).toHaveCount(0);
		} finally {
			for (const name of todos) {
				await api.remove_doc("ToDo", name);
			}
		}
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
			"#icon-sort-descending"
		);

		await order.click();
		await expect(order).toHaveAttribute("data-value", "asc");
		await expect(order).toHaveAttribute("title", "ascending");
		await expect(order.locator(".sort-order use")).toHaveAttribute(
			"href",
			"#icon-sort-ascending"
		);
	});
});

test.describe("List View bulk submit", () => {
	const doctype = "Bulk Submit Row";

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc(
			"DocType",
			{
				name: doctype,
				custom: 1,
				is_submittable: 1,
				module: "Custom",
				fields: [{ fieldname: "title", fieldtype: "Data", label: "Title" }],
				permissions: [
					{
						role: "System Manager",
						read: 1,
						write: 1,
						create: 1,
						delete: 1,
						submit: 1,
						cancel: 1,
					},
				],
			},
			true
		);
	});

	test("refreshes the list when a repeated submit fails", async ({ page, desk, api }) => {
		const selected = [];
		for (const title of ["first", "second"]) {
			const doc = await api.insert_doc(doctype, { title });
			selected.push(doc.name);
		}

		await desk.go_to_list(doctype);
		await desk.clear_filters();
		for (const name of selected) {
			await page.locator(`.list-row-checkbox[data-name="${name}"]`).click();
		}

		for (let run = 0; run < 2; run++) {
			await desk.click_action_button("Submit");
			await desk.click_modal_primary_button("Yes");
			await expect.poll(() => page.evaluate(() => cur_list.disable_list_update)).toBe(false);
		}
		await expect(page.locator(".modal:visible")).toContainText("Cannot submit");
		await expect
			.poll(() => page.evaluate(() => cur_list.get_checked_items(true).length))
			.toBe(selected.length);
	});
});
