import { test, expect } from "../support";

test.describe("Grid", () => {
	let original_log_settings_rows;

	test.afterEach(async ({ admin }) => {
		if (!original_log_settings_rows) return;
		const rows = original_log_settings_rows;
		original_log_settings_rows = null;
		await admin.update_doc("Log Settings", "Log Settings", { logs_to_clear: rows });
	});

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_contact_phone_nos_records");
	});

	test.beforeEach(async ({ page }) => {
		await page.goto("/app/contact/Test Contact");
		await page.waitForFunction(
			() =>
				window.cur_frm &&
				cur_frm.doc.name === "Test Contact" &&
				cur_frm.get_field("phone_nos")
		);
	});

	const get_table = (page, fieldname = "phone_nos") =>
		page.locator(`.frappe-control[data-fieldname="${fieldname}"]`);

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

	test("keeps child table in sync after backend removes a reordered row", async ({
		page,
		desk,
	}) => {
		await page.goto("/app/log-settings");
		await page.waitForFunction(() => window.cur_frm?.doctype === "Log Settings");
		original_log_settings_rows = await page.evaluate(() => {
			const original = cur_frm.doc.logs_to_clear.map((row) => ({
				ref_doctype: row.ref_doctype,
				days: row.days,
			}));
			cur_frm.add_child("logs_to_clear", { ref_doctype: "User", days: 30 });
			const rows = cur_frm.doc.logs_to_clear;
			rows.splice(1, 0, rows.pop());
			rows.forEach((row, i) => (row.idx = i + 1));
			cur_frm.refresh_field("logs_to_clear");
			return original;
		});

		await desk.save();
		await expect(page.locator(".modal-dialog", { hasText: "not supported" })).toBeVisible();
		await page.locator(".modal-dialog:visible .modal-header .btn-modal-close").click();

		const rows = await page.evaluate(() =>
			cur_frm.doc.logs_to_clear.map((row) => row.ref_doctype)
		);
		expect(rows).not.toContain("User");
		expect(rows.every(Boolean)).toBe(true);
		await expect(
			page.locator('.frappe-control[data-fieldname="logs_to_clear"] .grid-body .grid-row')
		).toHaveCount(rows.length);
	});
});
