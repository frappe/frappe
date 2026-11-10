import { test, expect } from "../support";

test.describe("Depends On", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_child_doctype", {
			name: "Child Test Depends On",
			fields: [
				{
					label: "Child Test Field",
					fieldname: "child_test_field",
					fieldtype: "Data",
					in_list_view: 1,
				},
				{
					label: "Child Dependant Field",
					fieldname: "child_dependant_field",
					fieldtype: "Data",
					in_list_view: 1,
				},
				{
					label: "Child Display Dependant Field",
					fieldname: "child_display_dependant_field",
					fieldtype: "Data",
					in_list_view: 1,
					depends_on: "eval:doc.child_test_field == 'show'",
				},
			],
		});
		await admin.call("frappe.tests.ui_test_helpers.create_doctype", {
			name: "Test Depends On",
			fields: [
				{
					label: "Test Field",
					fieldname: "test_field",
					fieldtype: "Data",
				},
				{
					label: "Dependant Field",
					fieldname: "dependant_field",
					fieldtype: "Data",
					mandatory_depends_on: "eval:doc.test_field=='Some Value'",
					read_only_depends_on: "eval:doc.test_field=='Some Other Value'",
				},
				{
					label: "Display Dependant Field",
					fieldname: "display_dependant_field",
					fieldtype: "Data",
					depends_on: "eval:doc.test_field=='Value'",
				},
				{
					label: "Child Test Depends On Field",
					fieldname: "child_test_depends_on_field",
					fieldtype: "Table",
					read_only_depends_on: "eval:doc.test_field=='Some Other Value'",
					options: "Child Test Depends On",
				},
				{
					label: "Dependent Tab",
					fieldname: "dependent_tab",
					fieldtype: "Tab Break",
					depends_on: "eval:doc.test_field=='Show Tab'",
				},
				{
					fieldname: "tab_section",
					fieldtype: "Section Break",
				},
				{
					label: "Field in Tab",
					fieldname: "field_in_tab",
					fieldtype: "Data",
				},
			],
		});
	});

	const test_field_value = (page) => page.evaluate(() => cur_frm.doc.test_field);

	test("should show the tab on other setting field value", async ({ page, desk }) => {
		await desk.new_form("Test Depends On");
		const test_field = await desk.fill_field("test_field", "Show Tab");
		await test_field.blur();
		await expect(page.getByRole("tab", { name: "Dependent Tab", exact: true })).toBeVisible();
	});

	test("should set the field as mandatory depending on other fields value", async ({
		page,
		desk,
	}) => {
		const save_button = page.getByRole("button", { name: "Save", exact: true });
		const missing_fields = page
			.locator(".msgprint-dialog .modal-title")
			.getByText("Missing Fields")
			.first();

		await desk.new_form("Test Depends On");
		await desk.fill_field("test_field", "Some Value");
		await expect.poll(() => test_field_value(page)).toBe("Some Value");
		await save_button.click();
		await expect(missing_fields).toBeVisible();
		await desk.hide_dialog();
		await desk.fill_field("test_field", "Random value");
		await expect.poll(() => test_field_value(page)).toContain("Random value");
		const saved = page.waitForResponse((res) =>
			res.url().includes("/api/method/frappe.desk.form.save.savedocs")
		);
		await save_button.click();
		expect((await saved).status()).toBe(200);
		await expect(missing_fields).toBeHidden();
	});

	test("should set the field as read only depending on other fields value", async ({
		page,
		desk,
	}) => {
		const dependant_field = page.locator('.control-input [data-fieldname="dependant_field"]');

		await desk.new_form("Test Depends On");
		await desk.fill_field("dependant_field", "Some Value");
		let test_field = await desk.fill_field("test_field", "Some Other Value");
		await test_field.blur();
		await expect(dependant_field).toBeDisabled();
		test_field = await desk.fill_field("test_field", "Random Value");
		await test_field.blur();
		await expect(dependant_field).toBeEnabled();
	});

	test("should set the table and its fields as read only depending on other fields value", async ({
		page,
		desk,
	}) => {
		await desk.new_form("Test Depends On");
		await desk.fill_field("dependant_field", "Some Value");
		const table = page.locator(
			'.frappe-control[data-fieldname="child_test_depends_on_field"]'
		);
		await table.getByRole("button", { name: "Add row", exact: true }).click();
		const row1 = table.locator('[data-idx="1"]');
		await row1.locator(".btn-open-row").click();
		const row1_form_in_grid = row1.locator(".form-in-grid");
		await expect(row1_form_in_grid.locator("input").first()).toBeFocused();
		const child_row = () =>
			page.evaluate(() => {
				const row = cur_frm.doc.child_test_depends_on_field[0];
				return [row.child_test_field, row.child_dependant_field];
			});
		const child_test_field = await desk.fill_table_field(
			"child_test_depends_on_field",
			"1",
			"child_test_field",
			"Some Value"
		);
		await child_test_field.blur();
		await expect.poll(child_row).toEqual(["Some Value", undefined]);
		const child_dependant_field = await desk.fill_table_field(
			"child_test_depends_on_field",
			"1",
			"child_dependant_field",
			"Some Other Value"
		);
		await child_dependant_field.blur();
		await expect.poll(child_row).toEqual(["Some Value", "Some Other Value"]);

		await row1_form_in_grid.locator(".grid-collapse-row").click();

		await desk.fill_field("test_field", "Some Other Value");
		await expect.poll(() => test_field_value(page)).toBe("Some Other Value");

		await row1.locator(".btn-open-row").click();

		const expected_values = {
			child_test_field: "Some Value",
			child_dependant_field: "Some Other Value",
		};
		for (const [fieldname, value] of Object.entries(expected_values)) {
			const control = row1_form_in_grid.locator(
				`.frappe-control[data-fieldname="${fieldname}"]`
			);
			await expect(control.locator(".control-value")).toHaveText(value);
			await expect(control.locator(".control-input")).toBeHidden();
			await expect(control.locator("input:enabled")).toHaveCount(0);
		}
	});

	test("should re-evaluate an on-grid column's depends_on when a sibling field is set programmatically", async ({
		page,
		desk,
	}) => {
		await desk.new_form("Test Depends On");
		const table = page.locator(
			'.frappe-control[data-fieldname="child_test_depends_on_field"]'
		);
		await table.getByRole("button", { name: "Add row", exact: true }).click();

		const hidden_due_to_dependency = () =>
			page.evaluate(() => {
				const cdn =
					cur_frm.fields_dict.child_test_depends_on_field.grid.grid_rows[0].doc.name;
				const df = frappe.meta.get_docfield(
					"Child Test Depends On",
					"child_display_dependant_field",
					cdn
				);
				return Boolean(df.hidden_due_to_dependency);
			});

		await expect.poll(hidden_due_to_dependency).toBe(true);

		await page.evaluate(() => {
			const { doctype: cdt, name: cdn } =
				cur_frm.fields_dict.child_test_depends_on_field.grid.grid_rows[0].doc;
			frappe.model.set_value(cdt, cdn, "child_test_field", "show");
		});

		await expect.poll(hidden_due_to_dependency).toBe(false);
	});

	test("should display the field depending on other fields value", async ({ page, desk }) => {
		const display_dependant_field = page.locator(
			'.control-input [data-fieldname="display_dependant_field"]'
		);

		await desk.new_form("Test Depends On");
		await expect(display_dependant_field).toBeHidden();
		await page.locator('.control-input [data-fieldname="test_field"]').clear();
		const test_field = await desk.fill_field("test_field", "Value");
		await test_field.blur();
		await expect(display_dependant_field).toBeVisible();
	});
});
