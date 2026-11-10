import { test, expect } from "../support";

test.describe("Grid Rich Text Column", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_child_doctype", {
			name: "Child Test Rich Text",
			fields: [
				{
					label: "Title",
					fieldname: "title",
					fieldtype: "Data",
					in_list_view: 1,
				},
				{
					label: "Content",
					fieldname: "content",
					fieldtype: "Text Editor",
					in_list_view: 1,
				},
			],
		});
		await admin.call("frappe.tests.ui_test_helpers.create_doctype", {
			name: "Test Rich Text Grid",
			fields: [
				{
					label: "Items",
					fieldname: "items",
					fieldtype: "Table",
					options: "Child Test Rich Text",
				},
			],
		});
	});

	test("shows stripped text instead of rendered HTML in static grid cells", async ({
		page,
		desk,
	}) => {
		await desk.new_form("Test Rich Text Grid");
		await page.evaluate(() => {
			cur_frm.add_child("items", {
				title: "Row 1",
				content: "<h1>Heading</h1><p><b>bold</b> and <i>italic</i></p>",
			});
			cur_frm.refresh_field("items");
		});

		const cell = page
			.locator('.frappe-control[data-fieldname="items"]')
			.locator('.grid-body .grid-row [data-fieldname="content"] .static-area');
		await expect(cell).toContainText("Heading");
		await expect(cell).toContainText("bold and italic");
		await expect(cell.locator("h1, b, i, .ql-editor")).toHaveCount(0);
	});
});
