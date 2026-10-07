import { test, expect } from "../support";
import doctype_with_child_table from "../fixtures/doctype_with_child_table";
import child_table_doctype from "../fixtures/child_table_doctype";
import child_table_doctype_1 from "../fixtures/child_table_doctype_1";

const doctype_with_child_table_name = doctype_with_child_table.name;

test.describe("Grid Row Dependency", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", child_table_doctype, true);
		await admin.insert_doc("DocType", child_table_doctype_1, true);
		await admin.insert_doc("DocType", doctype_with_child_table, true);
	});

	test.afterEach(async ({ api }) => {
		await api.call("frappe.model.utils.user_settings.save", {
			doctype: doctype_with_child_table_name,
			user_settings: JSON.stringify({ GridView: null }),
		});
	});

	test("keeps a dependent column on rows whose dependency is met", async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();

		await page.evaluate(
			(doctype) =>
				frappe.model.user_settings.save(doctype, "GridView", {
					"Child Table Doctype 1": [
						{ fieldname: "data", columns: 3 },
						{ fieldname: "dependent_data", columns: 3 },
					],
				}),
			doctype_with_child_table_name
		);

		await desk.new_form(doctype_with_child_table_name);

		await page.evaluate(() => {
			cur_frm.add_child("child_table_1", { data: "has data" });
			cur_frm.add_child("child_table_1", {});
			cur_frm.refresh();
		});

		const rows = page
			.locator('.frappe-control[data-fieldname="child_table_1"]')
			.locator(".grid-body .rows .grid-row");

		await rows.nth(1).locator(".data-row").click();
		await expect(rows.nth(1).locator('[data-fieldname="dependent_data"] input')).toHaveCount(
			0
		);

		await rows.nth(0).locator(".data-row").click();
		await expect(rows.nth(0).locator('[data-fieldname="dependent_data"] input')).toBeVisible();
	});
});
