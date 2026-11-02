import { test, expect } from "../support";

test.describe("Grid", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_contact_phone_nos_records");
	});

	test.beforeEach(async ({ page }) => {
		await page.goto("/desk/contact/Test Contact");
		await page.waitForFunction(
			() =>
				window.cur_frm &&
				cur_frm.doc.name === "Test Contact" &&
				cur_frm.get_field("phone_nos")
		);
	});

	const get_table = (page, fieldname = "phone_nos") =>
		page.locator(`.frappe-control[data-fieldname="${fieldname}"]`);

	const enable_bulk_edit = (page, enabled = true) =>
		page.evaluate((enabled) => {
			const grid = cur_frm.get_field("phone_nos").grid;
			grid.meta.allow_bulk_edit = enabled;
			grid.refresh_edit_rows_button();
		}, enabled);

	test("update docfield property using update_docfield_property", async ({ page }) => {
		const table = get_table(page);
		const table_form = page.locator(".grid-row-open");
		await page.evaluate(() =>
			cur_frm
				.get_field("phone_nos")
				.grid.update_docfield_property("is_primary_phone", "hidden", true)
		);

		for (const idx of [1, 2]) {
			await table.locator(`[data-idx="${idx}"] .btn-open-row`).click();
			await expect(
				table_form.locator('.frappe-control[data-fieldname="is_primary_phone"]')
			).toBeHidden();
			await table_form.locator(".grid-footer-toolbar").click();
		}
	});

	test("update docfield property using toggle_display", async ({ page }) => {
		const table = get_table(page);
		const table_form = page.locator(".grid-row-open");
		await page.evaluate(() =>
			cur_frm.get_field("phone_nos").grid.toggle_display("is_primary_mobile_no", false)
		);

		for (const idx of [1, 2]) {
			await table.locator(`[data-idx="${idx}"] .btn-open-row`).click();
			await expect(
				table_form.locator('.frappe-control[data-fieldname="is_primary_mobile_no"]')
			).toBeHidden();
			await table_form.locator(".grid-footer-toolbar").click();
		}
	});

	test("update docfield property using toggle_enable", async ({ page }) => {
		const table = get_table(page);
		const table_form = page.locator(".grid-row-open");
		await page.evaluate(() =>
			cur_frm.get_field("phone_nos").grid.toggle_enable("phone", false)
		);

		for (const idx of [1, 2]) {
			await table.locator(`[data-idx="${idx}"] .btn-open-row`).click();
			await expect(
				table_form.locator('.frappe-control[data-fieldname="phone"] .control-value')
			).toHaveClass(/(^|\s)like-disabled-input(\s|$)/);
			await table_form.locator(".grid-footer-toolbar").click();
		}
	});

	test("update docfield property using toggle_reqd", async ({ page, desk }) => {
		const table = get_table(page);
		const table_form = page.locator(".grid-row-open");
		await page.evaluate(() => cur_frm.get_field("phone_nos").grid.toggle_reqd("phone", false));

		for (const idx of [1, 2]) {
			await table.locator(`[data-idx="${idx}"] .btn-open-row`).click();
			await expect(table_form).toBeVisible();
			const phone_field = desk.get_field("phone");
			await phone_field.focus();
			await phone_field.clear();
			await phone_field.blur();
			await expect
				.poll(() =>
					page.evaluate((idx) => cur_frm.doc.phone_nos[idx - 1].phone || "", idx)
				)
				.toBe("");
			await expect(phone_field).not.toHaveClass(/(^|\s)has-error(\s|$)/);
			await table_form.locator(".grid-footer-toolbar").click();
		}
	});

	test("shows edit button only when child table allow_bulk_edit is enabled", async ({
		page,
	}) => {
		const table = get_table(page);

		await enable_bulk_edit(page, false);

		await table.locator('.grid-row[data-idx="1"] .grid-row-check').click();
		await expect(table.locator(".grid-edit-rows")).toHaveClass(/(^|\s)hidden(\s|$)/);

		await enable_bulk_edit(page, true);

		await expect(table.locator(".grid-edit-rows")).not.toHaveClass(/(^|\s)hidden(\s|$)/);
	});

	test("bulk edit updates only selected child rows", async ({ page }) => {
		const updated_phone = `99999${Date.now().toString().slice(-5)}`;
		const table = get_table(page);

		await enable_bulk_edit(page);
		const { row_count, phone_field_label, second_row_phone_before } = await page.evaluate(
			() => {
				const grid = cur_frm.get_field("phone_nos").grid;
				const phone_df = grid.docfields.find((df) => df.fieldname === "phone");
				return {
					row_count: cur_frm.doc.phone_nos.length,
					phone_field_label: phone_df && phone_df.label,
					second_row_phone_before: cur_frm.doc.phone_nos[1].phone || "",
				};
			}
		);
		expect(row_count).toBeGreaterThan(1);
		expect(phone_field_label).toBeTruthy();

		await table.locator('.grid-row[data-idx="1"] .grid-row-check').click();
		await table.locator(".grid-edit-rows").click();
		await page.waitForFunction(() => window.cur_dialog);

		await page.evaluate(
			async ([phone_field_label, updated_phone]) => {
				await cur_dialog.set_value("field", phone_field_label);
				await cur_dialog.set_value("value", updated_phone);
				cur_dialog.get_primary_btn().click();
			},
			[phone_field_label, updated_phone]
		);

		await expect
			.poll(() => page.evaluate(() => cur_frm.doc.phone_nos[0].phone))
			.toBe(updated_phone);
		expect(await page.evaluate(() => cur_frm.doc.phone_nos[1].phone || "")).toBe(
			second_row_phone_before
		);
	});

	test("shows bulk edit fields on submitted documents for allow-on-submit columns", async ({
		page,
	}) => {
		const table = get_table(page);

		await page.evaluate(() => {
			const grid = cur_frm.get_field("phone_nos").grid;
			grid.meta.allow_bulk_edit = true;
			grid.refresh_edit_rows_button();

			const phone_df = grid.docfields.find((df) => df.fieldname === "phone");
			phone_df.allow_on_submit = 1;
			cur_frm.doc.docstatus = 1;
		});

		await table.locator('.grid-row[data-idx="1"] .grid-row-check').click();
		await table.locator(".grid-edit-rows").click();

		const dialog = page.locator(".modal-dialog:visible");
		await expect(dialog.locator('.frappe-control[data-fieldname="field"]')).toBeVisible();
		await expect(dialog.locator('.frappe-control[data-fieldname="value"]')).toBeVisible();
	});

	test("hides add-row and add-multiple-rows buttons when rows are selected", async ({
		page,
	}) => {
		const table = get_table(page);
		const row_check = table.locator('.grid-row[data-idx="1"] .grid-row-check');

		await row_check.click();

		await expect(table.locator(".grid-add-row")).toHaveClass(/(^|\s)hidden(\s|$)/);
		await expect(table.locator(".grid-add-multiple-rows")).toHaveClass(/(^|\s)hidden(\s|$)/);

		await row_check.click();

		await expect(table.locator(".grid-add-row")).not.toHaveClass(/(^|\s)hidden(\s|$)/);
	});
});
