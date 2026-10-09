import { test, expect } from "../support";
import custom_submittable_doctype from "../fixtures/custom_submittable_doctype";
import doctype_without_report_permission from "../fixtures/doctype_without_report_permission";

// the page title is the last breadcrumb
const TITLE = ".navbar-breadcrumbs:visible li:last-child";

const doctype_name = custom_submittable_doctype.name;

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
		});

		// the group by controls refresh on their own, a second refresh() call would be throttled
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
