import { test, expect } from "../support";

test.describe("Business Modules", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_business_module_doctypes");
	});

	const field = (page, fieldname) =>
		page.locator(`.form-layout .frappe-control[data-fieldname="${fieldname}"]`);
	const column = (page, fieldname, table = "items") =>
		page.locator(
			`.frappe-control[data-fieldname="${table}"] .grid-heading-row .grid-static-col[data-fieldname="${fieldname}"]`
		);
	const hide_module_fields = (page, modules) =>
		page.evaluate((modules) => cur_frm.hide_module_fields(modules), modules);

	test("hides tagged fields when their module is off and shows them when it is on", async ({
		page,
		desk,
	}) => {
		await desk.new_form("Test Module Fields");
		await expect(field(page, "plain")).toBeVisible();
		await expect(field(page, "tagged")).toBeVisible();
		await expect(column(page, "tagged_col")).toBeVisible();

		await hide_module_fields(page, ["Stock"]);
		await expect(field(page, "plain")).toBeVisible();
		await expect(field(page, "tagged")).toBeHidden();
		await expect(column(page, "tagged_col")).toHaveCount(0);

		await hide_module_fields(page, []);
		await expect(field(page, "tagged")).toBeVisible();
		await expect(column(page, "tagged_col")).toBeVisible();
	});

	test("hides the column in every table of the same child doctype", async ({ page, desk }) => {
		await desk.new_form("Test Module Fields");
		await hide_module_fields(page, ["Stock"]);
		await expect(column(page, "tagged_col", "items")).toHaveCount(0);
		await expect(column(page, "tagged_col", "more_items")).toHaveCount(0);

		await hide_module_fields(page, []);
		await expect(column(page, "tagged_col", "items")).toBeVisible();
		await expect(column(page, "tagged_col", "more_items")).toBeVisible();
	});

	test("keeps hiding after the form refreshes", async ({ page, desk }) => {
		await desk.new_form("Test Module Fields");
		await hide_module_fields(page, ["Stock"]);
		await expect(field(page, "tagged")).toBeHidden();

		await page.evaluate(() => cur_frm.refresh());
		await expect(field(page, "tagged")).toBeHidden();
		await expect(field(page, "plain")).toBeVisible();
	});

	test("keeps a mandatory field visible", async ({ page, desk }) => {
		await desk.new_form("Test Module Fields");
		await page.evaluate(() => cur_frm.toggle_reqd("tagged", 1));
		await hide_module_fields(page, ["Stock"]);
		await expect(field(page, "tagged")).toBeVisible();
	});
});
