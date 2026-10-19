import { test, expect } from "../support";
import custom_submittable_doctype from "../fixtures/custom_submittable_doctype";
import doctype_without_report_permission from "../fixtures/doctype_without_report_permission";

// the page title is the last breadcrumb
const TITLE = ".navbar-breadcrumbs:visible li:last-child";

const doctype_name = custom_submittable_doctype.name;

function track_failed_report_requests(page) {
	const failed_requests = [];
	page.on("response", (response) => {
		if (response.url().includes("frappe.desk.reportview.get") && !response.ok()) {
			failed_requests.push(response.url());
		}
	});
	return failed_requests;
}

async function save_report_group_by({ desk, api }, doctype, group_by = null) {
	// the open view saves its own settings on render, let it finish before replacing them
	await desk.ready();
	const report = group_by
		? { group_by: { group_by, aggregates: [{ aggregate_function: "count" }] } }
		: {};
	await api.call("frappe.model.utils.user_settings.save", {
		doctype,
		user_settings: JSON.stringify({ Report: report }),
	});
}

test.describe("Report View", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", custom_submittable_doctype, true);
		const existing = await admin.get_list(doctype_name, ["name"], [["title", "=", "Doc 1"]]);
		for (const doc of existing.data) {
			await admin.set_value(doctype_name, doc.name, { enabled: 0 });
		}
		if (!existing.data.length) {
			await admin.insert_doc(doctype_name, {
				title: "Doc 1",
				description: "Random Text",
				enabled: 0,
				docstatus: 1,
			});
		}
	});

	test("drops a saved chart that has no Y axis", async ({ page, api, desk }) => {
		const errors = [];
		page.on("pageerror", (error) => errors.push(error.message));
		await page.goto(`/desk/List/${doctype_name}/Report`);
		// the open view saves its own settings on render, let it finish before replacing them
		await desk.ready();
		await api.call("frappe.model.utils.user_settings.save", {
			doctype: doctype_name,
			user_settings: JSON.stringify({
				Report: { chart_args: { chart_type: "bar", x_axis: "name", y_axes: [] } },
			}),
		});

		await page.reload();

		await expect(page.locator(".dt-row-0")).toBeVisible();
		await expect(page.locator(".charts-wrapper")).toBeHidden();
		expect(errors).toEqual([]);
	});

	test("Field with enabled allow_on_submit should be editable.", async ({ page, api }) => {
		const value_update = page.waitForResponse(
			(res) =>
				res.request().method() === "POST" &&
				res.url().includes("api/method/frappe.client.set_value")
		);
		await page.goto(`/desk/List/${doctype_name}/Report`);

		await expect(page.locator(".dt-row-0 > .dt-cell--col-3")).toContainText("Submitted");
		const cell = page.locator(".dt-row-0 > .dt-cell--col-4");

		await cell.dblclick();
		await cell.locator(".dt-cell__edit--col-4").getByRole("checkbox").check();
		await page.locator(".dt-row-0 > .dt-cell--col-3").click();

		await value_update;

		const r = await api.call("frappe.client.get_value", {
			doctype: doctype_name,
			filters: {
				title: "Doc 1",
			},
			fieldname: "enabled",
		});
		expect(r.message.enabled).toBe(1);
	});
});

test.describe("Report View without report permission", () => {
	const test_user = "test_report_permission@example.com";
	const role = "Report Permission Test Role";
	const list_route = "/desk/doctype-without-report-permission";

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("Role", { role_name: role, desk_access: 1 }, true);
		await admin.insert_doc("DocType", doctype_without_report_permission, true);
		await admin.call("frappe.tests.ui_test_helpers.create_test_user", { username: test_user });
		await admin.call("frappe.tests.ui_test_helpers.add_remove_role", {
			action: "add",
			user: test_user,
			role,
		});
	});

	test.beforeEach(async ({ desk }) => {
		await desk.login(test_user);
	});

	test("hides the report view and redirects its route to the list view", async ({ page }) => {
		await page.goto(`${list_route}/view/list`);

		await page.locator(".custom-btn-group.view-switcher button").click();
		const menu = page.locator(".es-menu[data-state='open']");
		await expect(menu).toContainText("Dashboard View");
		await expect(menu).not.toContainText("Report View");
		await page.keyboard.press("Escape");

		await page.goto(`${list_route}/view/report`);
		await expect.poll(() => page.evaluate(() => window.cur_list?.view_name)).toBe("List");
		await expect(page).not.toHaveURL(/\/view\/report/);
	});

	test("opens the list view when the doctype defaults to the report view", async ({ page }) => {
		await page.goto(list_route);
		await expect.poll(() => page.evaluate(() => window.cur_list?.view_name)).toBe("List");
		await expect(page.locator(TITLE)).toContainText("DocType Without Report Permission");
	});
});

test.describe("Report View group by button", () => {
	const test_user = "test_report_group_by@example.com";
	const role = "Report Group By Test Role";
	const doctype = "Report Group By Label";
	const label = "Category <b>bold</b>";

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("Role", { role_name: role, desk_access: 1 }, true);
		await admin.insert_doc(
			"DocType",
			{
				name: doctype,
				custom: 1,
				module: "Custom",
				fields: [
					{ fieldname: "category", fieldtype: "Data", label },
					{ fieldname: "amount", fieldtype: "Float", label: "Amount" },
				],
				permissions: [{ role, read: 1, report: 1 }],
			},
			true
		);
		await admin.call("frappe.tests.ui_test_helpers.create_test_user", { username: test_user });
		await admin.call("frappe.tests.ui_test_helpers.add_remove_role", {
			action: "add",
			user: test_user,
			role,
		});
		await admin.insert_doc(doctype, { category: "A", amount: 10.25 });
		await admin.insert_doc(doctype, { category: "B", amount: 20.25 });
	});

	test.beforeEach(async ({ desk, page }) => {
		await desk.login(test_user);
		await page.goto("/desk/report-group-by-label/view/report");
		// group by is set up and the ungrouped first load is done once rows render
		await expect(page.locator(".dt-row-0")).toBeVisible();
	});

	test("shows the group by field label as text", async ({ page }) => {
		await page.evaluate(() =>
			window.cur_list.group_by_control.apply_settings({
				group_by: ["`tabReport Group By Label`.`category`"],
				aggregates: [{ aggregate_function: "count" }],
			})
		);

		const button_label = page.locator(".group-by-button .button-label");
		await expect(button_label).toContainText(label);
		await expect(button_label.locator("b")).toHaveCount(0);
	});

	test("keeps keyboard focus in the group by popover", async ({ page }) => {
		const button = page.locator(".group-by-button");
		const popover = page.locator(".group-by-popover");
		const input = popover.locator(".group-by-field-select input").first();
		await page.evaluate(() => window.cur_list.group_by_control.remove_group_by());

		await button.click();
		await expect(input).toBeFocused();
		await expect(popover.locator("li", { hasText: "Category" })).toBeVisible();

		// picking the first group by re-renders the popover, focus moves on to the row
		await input.pressSequentially("Category");
		await input.press("Enter");
		await expect(popover.locator(".remove-group-by-row").first()).toBeFocused();

		// reopening focuses the popover, Tab reaches the field and another Tab keeps it
		await button.click();
		await expect(popover).toBeHidden();
		await button.click();
		await expect(popover).toBeFocused();
		await page.keyboard.press("Tab");
		await expect(input).toBeFocused();
		await page.keyboard.press("Tab");
		await expect(input).toHaveValue(label);
		expect(
			await page.evaluate(() => window.cur_list.group_by_control.get_group_bys())
		).toEqual([{ doctype, fieldname: "category" }]);

		// re-rendering for aggregate changes keeps focus on the changed or added control
		const aggregate_function = popover.locator("select.aggregate-function");
		await aggregate_function.first().focus();
		await aggregate_function.first().selectOption("sum");
		await expect(aggregate_function.first()).toBeFocused();
		await popover.locator(".add-aggregate").focus();
		await page.keyboard.press("Enter");
		await expect(aggregate_function).toHaveCount(2);
		await expect(aggregate_function.last()).toBeFocused();

		// Escape outside a field closes the popover and returns focus to the button
		await popover.locator(".remove-group-by-row").first().focus();
		await page.keyboard.press("Escape");
		await expect(popover).toBeHidden();
		await expect(button).toBeFocused();

		// so does Enter on the apply button
		await page.keyboard.press("Enter");
		await expect(popover).toBeFocused();
		await popover.locator(".apply-group-by").focus();
		await page.keyboard.press("Enter");
		await expect(popover).toBeHidden();
		await expect(button).toBeFocused();

		// removing a row keeps focus in the popover, so Escape still closes it
		await page.keyboard.press("Enter");
		await expect(popover).toBeFocused();
		await popover.locator(".remove-group-by-row").first().focus();
		await page.keyboard.press("Enter");
		await expect(popover).toBeFocused();
		await page.keyboard.press("Escape");
		await expect(popover).toBeHidden();
	});

	test("opens a saved view grouped by a field that cannot be queried", async ({
		page,
		api,
		desk,
	}) => {
		const failed_requests = track_failed_report_requests(page);
		const open_with_saved_group_by = async (group_by) => {
			await save_report_group_by({ desk, api }, doctype, group_by);
			await page.goto("/desk/report-group-by-label/view/report");
			await expect(page.locator(".dt-row-0")).toBeVisible();
		};
		const comments = "`tabReport Group By Label`.`_comments`";
		const category = "`tabReport Group By Label`.`category`";

		try {
			await open_with_saved_group_by([comments, category]);
			expect(await page.evaluate(() => window.cur_list.group_by_control.group_by)).toBe(
				category
			);
			await expect
				.poll(() =>
					page.evaluate(() => window.cur_list.data.map((row) => row.category).sort())
				)
				.toEqual(["A", "B"]);

			await open_with_saved_group_by([comments]);
			expect(
				await page.evaluate(() => window.cur_list.group_by_control.group_by)
			).toBeFalsy();

			expect(failed_requests).toEqual([]);
		} finally {
			await save_report_group_by({ desk, api }, doctype);
		}
	});

	test("keeps decimals in minimum and maximum totals", async ({ page }) => {
		await page.evaluate(() => {
			const amount = "`tabReport Group By Label`.`amount`";
			window.cur_list.add_totals_row = 1;
			window.cur_list.group_by_control.apply_settings({
				group_by: ["`tabReport Group By Label`.`category`"],
				aggregates: [
					{ aggregate_function: "min", aggregate_on: amount },
					{ aggregate_function: "max", aggregate_on: amount },
				],
			});
			// the group by controls may already have started this refresh, then refresh() resolves
			// before the grouped rows arrive, so poll for them instead of awaiting it
			window.cur_list.refresh();
		});

		await expect
			.poll(() =>
				page.evaluate(() => {
					const totals = window.cur_list.get_columns_totals(window.cur_list.data);
					return [totals._aggregate_column, totals._aggregate_column_1];
				})
			)
			.toEqual([10.25, 20.25]);
	});
});

test.describe("Report View child table group by", () => {
	const test_user = "test_report_child_group_by@example.com";
	const role = "Report Child Group By Test Role";
	const doctype = "Report Child Group By Parent";
	const child_doctype = "Report Child Group By Row";

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("Role", { role_name: role, desk_access: 1 }, true);
		await admin.insert_doc(
			"DocType",
			{
				name: child_doctype,
				custom: 1,
				istable: 1,
				module: "Custom",
				fields: [
					{ fieldname: "label", fieldtype: "Data", label: "Label" },
					{ fieldname: "note", fieldtype: "Data", label: "Note", is_virtual: 1 },
				],
			},
			true
		);
		await admin.insert_doc(
			"DocType",
			{
				name: doctype,
				custom: 1,
				module: "Custom",
				fields: [
					{ fieldname: "label", fieldtype: "Data", label: "Label", is_virtual: 1 },
					{
						fieldname: "rows",
						fieldtype: "Table",
						label: "Rows",
						options: child_doctype,
					},
				],
				permissions: [{ role, read: 1, report: 1 }],
			},
			true
		);
		await admin.call("frappe.tests.ui_test_helpers.create_test_user", { username: test_user });
		await admin.call("frappe.tests.ui_test_helpers.add_remove_role", {
			action: "add",
			user: test_user,
			role,
		});
		await admin.insert_doc(doctype, { rows: [{ label: "A" }, { label: "B" }] });
	});

	test("checks the virtual flag on the child table", async ({ page, api, desk }) => {
		await desk.login(test_user);
		await page.goto("/desk/report-child-group-by-parent/view/report");
		await expect(page.locator(".dt-row-0")).toBeVisible();

		const failed_requests = track_failed_report_requests(page);
		const open_with_saved_group_by = async (group_by) => {
			await save_report_group_by({ desk, api }, doctype, group_by);
			await page.goto("/desk/report-child-group-by-parent/view/report");
			await expect(page.locator(".dt-row-0")).toBeVisible();
		};
		const child_label = "`tabReport Child Group By Row`.`label`";
		const child_note = "`tabReport Child Group By Row`.`note`";

		try {
			// the parent has a virtual field of the same name, the child field is stored
			await open_with_saved_group_by([child_label]);
			expect(await page.evaluate(() => window.cur_list.group_by_control.group_by)).toBe(
				child_label
			);
			await expect.poll(() => page.evaluate(() => window.cur_list.data.length)).toBe(2);

			await open_with_saved_group_by([child_note]);
			expect(
				await page.evaluate(() => window.cur_list.group_by_control.group_by)
			).toBeFalsy();

			expect(failed_requests).toEqual([]);
		} finally {
			await save_report_group_by({ desk, api }, doctype);
		}
	});
});
