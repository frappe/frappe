import { test, expect } from "../support";

const root_doctype = "Nested Grid Test Parent";
const child_doctype = "Nested Grid Test Child";
const grandchild_doctype = "Nested Grid Test Detail";

async function open_doc(page, desk, name) {
	await page.goto("/desk/nested-grid-test-parent/" + encodeURIComponent(name));
	await desk.ready();
}

async function open_child(page) {
	await page
		.locator('.frappe-control[data-fieldname="rows"] .grid-row[data-idx="1"] .btn-open-row')
		.first()
		.click();
	return page.locator('.grid-row-open .frappe-control[data-fieldname="details"]').first();
}

test.describe("Nested child table", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_child_doctype", {
			name: grandchild_doctype,
			fields: [{ label: "Value", fieldname: "value", fieldtype: "Data", in_list_view: 1 }],
		});
		await admin.call("frappe.tests.ui_test_helpers.create_child_doctype", {
			name: child_doctype,
			fields: [
				{ label: "Label", fieldname: "label", fieldtype: "Data", in_list_view: 1 },
				{
					label: "Details",
					fieldname: "details",
					fieldtype: "Table",
					options: grandchild_doctype,
				},
			],
		});
		await admin.insert_doc(
			"DocType",
			{
				name: root_doctype,
				module: "Core",
				custom: 1,
				autoname: "field:title",
				fields: [
					{ label: "Title", fieldname: "title", fieldtype: "Data", reqd: 1 },
					{
						label: "Rows",
						fieldname: "rows",
						fieldtype: "Table",
						options: child_doctype,
					},
				],
				permissions: [{ role: "System Manager", read: 1, write: 1, create: 1, delete: 1 }],
			},
			true
		);
	});

	test("clears grandchildren when sync replaces a child row", async ({ page, desk, admin }) => {
		const title = "Nested row replacement " + Date.now();
		await admin.insert_doc(root_doctype, {
			title,
			rows: [{ details: [{ value: "old detail" }] }],
		});
		await open_doc(page, desk, title);
		const result = await page.evaluate(() => {
			const row = cur_frm.doc.rows[0];
			const old_name = row.name;
			const detail_name = row.details[0].name;
			const new_name = "replacement-" + Date.now();
			frappe.model.sync({
				...cur_frm.doc,
				rows: [{ ...row, name: new_name, details: [] }],
			});
			return {
				same_row: cur_frm.doc.rows[0] === row,
				renamed: row.name === new_name,
				cleared: row.details.length === 0,
				old_removed: !locals["Nested Grid Test Child"][old_name],
				new_present: locals["Nested Grid Test Child"][new_name] === row,
				detail_removed: !locals["Nested Grid Test Detail"][detail_name],
			};
		});
		expect(result).toEqual({
			same_row: true,
			renamed: true,
			cleared: true,
			old_removed: true,
			new_present: true,
			detail_removed: true,
		});
	});

	test("adds, edits, and removes grandchildren across reloads", async ({ page, desk }) => {
		const title = "Nested grid " + Date.now();
		await desk.new_form(root_doctype);
		await desk.fill_field("title", title);
		await page.locator('.frappe-control[data-fieldname="rows"] .grid-add-row').first().click();
		let details = await open_child(page);
		await details.locator(".grid-add-row").first().click();
		await details.locator('.grid-row[data-idx="1"] .btn-open-row').first().click();
		await expect(page.locator(".grid-row-open")).toHaveCount(2);
		const value = details.locator(
			'.grid-row-open .frappe-control[data-fieldname="value"] input'
		);
		await value.fill("nested value");
		await value.blur();
		await desk.save();

		await open_doc(page, desk, title);
		details = await open_child(page);
		await expect
			.poll(() => page.evaluate(() => cur_frm.doc.rows[0].details[0].value))
			.toBe("nested value");
		await page.evaluate(() => {
			window.__nested_detail_events = 0;
			frappe.ui.form.on(
				"Nested Grid Test Detail",
				"value",
				() => window.__nested_detail_events++
			);
		});
		await details.locator('.grid-row[data-idx="1"] .btn-open-row').first().click();
		const edited = details.locator(
			'.grid-row-open .frappe-control[data-fieldname="value"] input'
		);
		await edited.fill("edited value");
		await edited.blur();
		await expect.poll(() => page.evaluate(() => cur_frm.is_dirty())).toBe(true);
		await expect
			.poll(() => page.evaluate(() => window.__nested_detail_events))
			.toBeGreaterThan(0);
		await desk.save();

		await open_doc(page, desk, title);
		await expect
			.poll(() => page.evaluate(() => cur_frm.doc.rows[0].details[0].value))
			.toBe("edited value");
		await open_child(page);
		await page.evaluate(() => {
			const parent = cur_frm.doc.rows[0];
			const grid = cur_frm.fields_dict.rows.grid.get_row(parent.name).grid_form.layout
				.fields_dict.details.grid;
			grid.get_row(parent.details[0].name).remove();
		});
		await desk.save();
		await open_doc(page, desk, title);
		await expect.poll(() => page.evaluate(() => cur_frm.doc.rows[0].details.length)).toBe(0);
	});

	test("deletes nested rows while preserving siblings", async ({ page, desk, admin }) => {
		const title = "Nested bulk delete " + Date.now();
		await admin.insert_doc(root_doctype, {
			title,
			rows: [
				{ details: [{ value: "first" }, { value: "second" }] },
				{ details: [{ value: "keep" }] },
			],
		});
		await open_doc(page, desk, title);
		await open_child(page);
		const result = await page.evaluate(() => {
			const [row, sibling] = cur_frm.doc.rows;
			const names = row.details.map((detail) => detail.name);
			const sibling_name = sibling.details[0].name;
			const grid = cur_frm.fields_dict.rows.grid.get_row(row.name).grid_form.layout
				.fields_dict.details.grid;
			frappe.confirm = (_message, confirm) => confirm();
			grid.delete_all_rows();
			return {
				removed: names.every((name) => !locals["Nested Grid Test Detail"][name]),
				kept: Boolean(locals["Nested Grid Test Detail"][sibling_name]),
			};
		});
		expect(result).toEqual({ removed: true, kept: true });
		await desk.save();
		await open_doc(page, desk, title);
		await expect
			.poll(() =>
				page.evaluate(() => cur_frm.doc.rows.map((row) => row.details.map((d) => d.value)))
			)
			.toEqual([[], ["keep"]]);
	});

	test("persists grandchild row order", async ({ page, desk, admin }) => {
		const title = "Nested reorder " + Date.now();
		await admin.insert_doc(root_doctype, {
			title,
			rows: [{ details: [{ value: "first" }, { value: "second" }] }],
		});
		await open_doc(page, desk, title);
		const details = await open_child(page);
		await expect(details.locator(".grid-body .grid-row[data-idx]")).toHaveCount(2);
		await details
			.locator('.grid-row[data-idx="1"] .sortable-handle')
			.dragTo(details.locator('.grid-row[data-idx="2"]'));
		const order = () =>
			page.evaluate(() => cur_frm.doc.rows[0].details.map((d) => [d.value, d.idx]));
		await expect.poll(order).toEqual([
			["second", 1],
			["first", 2],
		]);
		await desk.save();
		await open_doc(page, desk, title);
		await expect.poll(order).toEqual([
			["second", 1],
			["first", 2],
		]);
	});

	test("deletes grandchildren with all parent rows", async ({ page, desk, admin }) => {
		const title = "Nested parent bulk delete " + Date.now();
		await admin.insert_doc(root_doctype, {
			title,
			rows: [{ details: [{ value: "first" }] }, { details: [{ value: "second" }] }],
		});
		await open_doc(page, desk, title);
		const result = await page.evaluate(() => {
			const children = cur_frm.doc.rows.map((row) => row.name);
			const grandchildren = cur_frm.doc.rows.flatMap((row) =>
				row.details.map((d) => d.name)
			);
			frappe.confirm = (_message, confirm) => confirm();
			cur_frm.fields_dict.rows.grid.delete_all_rows();
			return {
				rows: cur_frm.doc.rows.length,
				children_removed: children.every(
					(name) => !locals["Nested Grid Test Child"][name]
				),
				grandchildren_removed: grandchildren.every(
					(name) => !locals["Nested Grid Test Detail"][name]
				),
			};
		});
		expect(result).toEqual({ rows: 0, children_removed: true, grandchildren_removed: true });
		await desk.save();
		await open_doc(page, desk, title);
		await expect.poll(() => page.evaluate(() => cur_frm.doc.rows.length)).toBe(0);
	});
});
