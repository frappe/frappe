import { test, expect } from "../support";
import doctype_with_child_table from "../fixtures/doctype_with_child_table";
import child_table_doctype from "../fixtures/child_table_doctype";
import child_table_doctype_1 from "../fixtures/child_table_doctype_1";

const doctype_with_child_table_name = doctype_with_child_table.name;

test.describe("Grid Search", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", child_table_doctype, true);
		await admin.insert_doc("DocType", child_table_doctype_1, true);
		await admin.insert_doc("DocType", doctype_with_child_table, true);
		await admin.call("frappe.tests.ui_test_helpers.insert_doctype_with_child_table_record", {
			name: doctype_with_child_table_name,
		});
	});

	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();
		await page.evaluate(() =>
			frappe.model.user_settings.save("Doctype With Child Table", "GridView", {
				"Child Table Doctype 1": [
					{ fieldname: "data", columns: 2 },
					{ fieldname: "barcode", columns: 1 },
					{ fieldname: "check", columns: 1 },
					{ fieldname: "rating", columns: 2 },
					{ fieldname: "duration", columns: 2 },
					{ fieldname: "date", columns: 2 },
				],
			})
		);
		await page.goto("/desk/doctype-with-child-table/Test Grid Search");
	});

	const get_table = (page) => page.locator('.frappe-control[data-fieldname="child_table_1"]');
	const get_rows = (table) => table.locator(".grid-body .rows .grid-row");
	const get_search = (table, fieldtype) =>
		table.locator(`.grid-heading-row .search input[data-fieldtype="${fieldtype}"]`);

	test("Test search row visibility", async ({ page }) => {
		const table = get_table(page);
		await table.locator(".grid-row-check").last().click();
		await table.locator(".grid-footer").getByText("Delete").first().click();
		await expect(page.locator(".grid-heading-row .grid-row .search")).toHaveCount(0);
	});

	test("test search field for different fieldtypes", async ({ page }) => {
		const table = get_table(page);
		const rows = get_rows(table);

		const index_search = table.locator(".grid-heading-row .row-index.search input");
		await index_search.pressSequentially("3");
		await expect(rows).toHaveCount(2);
		await index_search.clear();

		await get_search(table, "Data").pressSequentially("Data");
		await expect(rows).toHaveCount(1);
		await get_search(table, "Data").clear();

		await get_search(table, "Barcode").pressSequentially("092");
		await expect(rows).toHaveCount(4);
		await get_search(table, "Barcode").clear();

		await get_search(table, "Check").pressSequentially("1");
		await expect(rows).toHaveCount(9);
		await get_search(table, "Check").clear();

		await get_search(table, "Check").pressSequentially("0");
		await expect(rows).toHaveCount(11);
		await get_search(table, "Check").clear();

		await get_search(table, "Rating").pressSequentially("3");
		await expect(rows).toHaveCount(3);
		await get_search(table, "Rating").clear();

		await get_search(table, "Duration").pressSequentially("3d");
		await expect(rows).toHaveCount(3);
		await get_search(table, "Duration").clear();

		await get_search(table, "Date").pressSequentially("2022");
		await expect(rows).toHaveCount(4);
		await get_search(table, "Date").clear();
	});

	test("test with multiple filter", async ({ page }) => {
		const table = get_table(page);
		const rows = get_rows(table);

		await get_search(table, "Data").pressSequentially("a");
		await expect(rows).toHaveCount(10);

		await get_search(table, "Barcode").pressSequentially("0");
		await expect(rows).toHaveCount(8);

		await get_search(table, "Duration").pressSequentially("d");
		await expect(rows).toHaveCount(5);

		await get_search(table, "Date").pressSequentially("02-");
		await expect(rows).toHaveCount(2);
	});
});
