import { test, expect } from "../support";
import custom_submittable_doctype from "../fixtures/custom_submittable_doctype";

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
		await page.goto(`/app/List/${doctype_name}/Report`);

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

test.describe("Report View selection", () => {
	const doctype = "Report Selection Row";

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc(
			"DocType",
			{
				name: doctype,
				custom: 1,
				module: "Custom",
				sort_field: "title",
				sort_order: "ASC",
				fields: [{ fieldname: "title", fieldtype: "Data", label: "Title" }],
				permissions: [
					{ role: "System Manager", read: 1, write: 1, create: 1, delete: 1, report: 1 },
				],
			},
			true
		);
		const existing = await admin.get_list(doctype, ["name"]);
		for (const doc of existing.data) {
			await admin.remove_doc(doctype, doc.name);
		}
		await admin.insert_doc(doctype, { title: "B" });
		await admin.insert_doc(doctype, { title: "C" });
	});

	test("keeps the same document selected after a bulk edit", async ({ page, desk }) => {
		await page.goto("/app/report-selection-row/view/report");
		await expect(page.locator(".dt-row-1")).toBeVisible();
		const selected = await page.evaluate(() => cur_list.data[1].name);
		await page.locator(".dt-row-1 .dt-cell--col-0 input[type='checkbox']").click();

		// renaming "C" to "A" moves the selected row to the top
		await desk.click_action_button("Edit");
		await page.waitForFunction(() => cur_dialog?.display);
		await page.evaluate(async () => {
			await cur_dialog.set_value("field", "Title");
			await cur_dialog.set_value("value", "A");
			// refresh() skips a repeat of the same query within 3 seconds of the page load
			cur_list.last_args = null;
		});
		await desk.click_modal_primary_button("Update 1 records");
		await expect(page.locator(".modal:visible")).toHaveCount(0);

		await expect.poll(() => page.evaluate(() => cur_list.data[0].name)).toBe(selected);
		expect(await page.evaluate(() => cur_list.get_checked_items(true))).toEqual([selected]);
		await expect(
			page.locator(".dt-row-0 .dt-cell--col-0 input[type='checkbox']")
		).toBeChecked();
		await expect(
			page.locator(".dt-row-1 .dt-cell--col-0 input[type='checkbox']")
		).not.toBeChecked();
	});
});

test.describe("Report View selection with child table column", () => {
	const doctype = "Report Selection Parent";
	const child_doctype = "Report Selection Child";

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc(
			"DocType",
			{
				name: child_doctype,
				custom: 1,
				istable: 1,
				module: "Custom",
				fields: [{ fieldname: "label", fieldtype: "Data", label: "Label" }],
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
					{ fieldname: "title", fieldtype: "Data", label: "Title" },
					{
						fieldname: "rows",
						fieldtype: "Table",
						label: "Rows",
						options: child_doctype,
					},
				],
				permissions: [
					{ role: "System Manager", read: 1, write: 1, create: 1, delete: 1, report: 1 },
				],
			},
			true
		);
		const existing = await admin.get_list(doctype, ["name"]);
		for (const doc of existing.data) {
			await admin.remove_doc(doctype, doc.name);
		}
		await admin.insert_doc(doctype, {
			title: "A",
			rows: [{ label: "one" }, { label: "two" }, { label: "three" }],
		});
	});

	test("keeps only the checked child row selected after a refresh", async ({ page }) => {
		await page.goto("/app/report-selection-parent/view/report");
		await expect(page.locator(".dt-row-0")).toBeVisible();
		// the column is saved in user settings, so a rerun already has it
		await page.evaluate(() => {
			if (!cur_list.fields.some(([, dt]) => dt === "Report Selection Child")) {
				cur_list.add_column_to_datatable("label", "Report Selection Child", 2);
			}
		});
		await expect(page.locator(".dt-row-2")).toBeVisible();

		await page.locator(".dt-row-1 .dt-cell--col-0 input[type='checkbox']").click();
		const reloaded = page.waitForResponse((r) =>
			r.url().includes("frappe.desk.reportview.get")
		);
		await page.evaluate(() => {
			cur_list.last_args = null;
			cur_list.refresh();
		});
		await reloaded;
		await page.evaluate(() => frappe.after_ajax());

		expect(await page.evaluate(() => cur_list.datatable.rowmanager.getCheckedRows())).toEqual([
			"1",
		]);
	});
});
