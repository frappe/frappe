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

	test.describe("Touch selection", () => {
		test.use({
			hasTouch: true,
			userAgent:
				"Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Mobile Safari/537.36",
		});
		test.beforeEach(({ browserName }) => {
			test.skip(browserName !== "chromium", "Touch gestures use Chromium's input protocol");
		});

		const touch = (session, type, point) =>
			session.send("Input.dispatchTouchEvent", { type, touchPoints: point ? [point] : [] });

		test("selects rows on taps and cancels dragging on early movement", async ({ page }) => {
			const table = get_table(page);
			const checkbox = table.locator('.grid-row[data-idx="1"] .grid-row-check');
			await checkbox.scrollIntoViewIfNeeded();
			const box = await checkbox.boundingBox();
			const point = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
			const session = await page.context().newCDPSession(page);
			try {
				for (const [duration, movement] of [
					[100, 0],
					[200, 1],
					[300, 5],
				]) {
					const checked = await checkbox.isChecked();
					await touch(session, "touchStart", point);
					await touch(session, "touchMove", { x: point.x, y: point.y + movement });
					await page.waitForTimeout(duration);
					expect(await table.locator(".sortable-chosen").count()).toBe(0);
					await touch(session, "touchEnd");
					await expect(checkbox).toBeChecked({ checked: !checked });
					await expect
						.poll(() =>
							page.evaluate(() => Boolean(cur_frm.doc.phone_nos[0].__checked))
						)
						.toBe(!checked);
				}
			} finally {
				await session.detach();
			}
		});

		test("keeps mouse dragging immediate", async ({ page }) => {
			const rows = get_table(page).locator(".grid-body .grid-row");
			const second_row_name = await rows.nth(1).getAttribute("data-name");
			const handle = rows.first().locator(".row-index");
			await handle.scrollIntoViewIfNeeded();
			const box = await handle.boundingBox();
			const target = await rows.nth(1).boundingBox();
			await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
			await page.mouse.down();
			try {
				expect(await rows.first().getAttribute("class")).toContain("sortable-chosen");
				await page.mouse.move(box.x + box.width / 2, target.y + target.height - 5, {
					steps: 5,
				});
				await expect
					.poll(() => rows.first().getAttribute("data-name"))
					.toBe(second_row_name);
			} finally {
				await page.mouse.up();
			}
		});

		test("drags from the checkbox after a hold when row numbers are hidden", async ({
			page,
		}) => {
			const table = get_table(page);
			await table.evaluate((element) => element.classList.add("form-column", "col-sm-6"));
			const rows = table.locator(".grid-body .grid-row");
			await expect(rows.first().locator(".row-index")).toBeHidden();
			const checkbox = rows.first().locator(".grid-row-check");
			await checkbox.scrollIntoViewIfNeeded();
			const checked = await checkbox.isChecked();
			const first_row_name = await rows.first().getAttribute("data-name");
			const second_row_name = await rows.nth(1).getAttribute("data-name");
			const box = await checkbox.boundingBox();
			const target = await rows.nth(1).boundingBox();
			const point = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
			const session = await page.context().newCDPSession(page);
			try {
				await touch(session, "touchStart", point);
				await touch(session, "touchMove", { x: point.x, y: point.y + 1 });
				await page.waitForTimeout(300);
				await expect(rows.first()).toHaveClass(/sortable-chosen/);
				for (const fraction of [0.25, 0.5, 0.75, 1]) {
					await touch(session, "touchMove", {
						x: point.x,
						y: point.y + (target.y + target.height - 5 - point.y) * fraction,
					});
					await page.evaluate(() => new Promise(requestAnimationFrame));
				}
				await expect
					.poll(() => rows.first().getAttribute("data-name"))
					.toBe(second_row_name);
				await touch(session, "touchEnd");
				await expect(
					table.locator(`.grid-row[data-name="${first_row_name}"] .grid-row-check`)
				).toBeChecked({ checked });
			} finally {
				await session.detach();
			}
		});
	});

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

	test("parks the Link dropdown on the grid and puts it back when it closes", async ({
		page,
	}) => {
		const table = get_table(page, "links");
		await table.scrollIntoViewIfNeeded();
		// the drift comes from page scroll, so scroll .main-section: Desk never scrolls the window
		await expect
			.poll(() => table.evaluate((el) => el.closest(".main-section").scrollTop))
			.toBeGreaterThan(100);

		await table.locator(".grid-add-row").click();
		// the cell renders its control only once the row turns editable
		await table.locator('.grid-row[data-idx="1"] [data-fieldname="link_doctype"]').click();
		const cell = table.locator(
			'.grid-row[data-idx="1"] [data-fieldname="link_doctype"] input'
		);
		await cell.pressSequentially("User");

		// the cell clips the dropdown, so it opens parked on the grid instead
		const parked = table.locator(".grid-field > .awesomplete");
		await expect(parked.locator("ul")).toBeVisible();

		const parked_box = await parked.evaluate((el) => el.getBoundingClientRect().toJSON());
		const cell_box = await cell.evaluate((el) => el.getBoundingClientRect().toJSON());
		expect(parked_box.top - cell_box.top).toBeGreaterThanOrEqual(0);
		expect(parked_box.top - cell_box.top).toBeLessThanOrEqual(100);
		expect(Math.abs(parked_box.left - cell_box.left)).toBeLessThanOrEqual(5);

		await cell.press("Escape");

		await expect(table.locator(".grid-field > .awesomplete")).toHaveCount(0);
	});
});
