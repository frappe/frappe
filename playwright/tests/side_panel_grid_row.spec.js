import { test, expect } from "../support";

// The side panel renders its document in a frm-less frappe.ui.form.Layout (side_panel.js), so
// a child table row has no live frm to open the native in-grid edit form against. Opening it
// anyway used to leave it permanently stuck: its toolbar is hidden (read-only grid) and its
// freeze backdrop's only close path is cur_frm.cur_grid, which never fires without a frm.
test.describe("Side Panel Grid Row", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_contact_phone_nos_records");
	});

	test.beforeEach(async ({ page, desk }) => {
		// Any ordinary desk page works: what matters is that it has no cur_frm of its own,
		// matching how the side panel is actually opened from a report or list view.
		await desk.go_to_list("Contact");
		await desk.ready();

		await page.evaluate(
			() =>
				new Promise((resolve) => {
					frappe.require("side_panel.bundle.js").then(() => {
						frappe.ui.get_side_panel().open("Contact", "Test Contact");
						resolve();
					});
				})
		);
		await expect(page.locator(".side-panel")).toHaveClass(/is-open/);
		await expect(page.locator(".side-panel .side-panel-doc.is-ready")).toBeAttached();
	});

	const get_row = (page) =>
		page
			.locator('.side-panel .frappe-control[data-fieldname="phone_nos"] .rows .grid-row')
			.first();

	test("clicking a row opens a closeable dialog, not the stuck native form", async ({ page }) => {
		await get_row(page).click();

		await expect(page.locator(".side-panel-row-dialog")).toBeVisible();
		// the broken surface must never appear at all
		await expect(page.locator(".grid-row-open")).toHaveCount(0);
		await expect(page.locator("#freeze")).toHaveCount(0);

		await page.locator(".side-panel-row-dialog .btn-modal-close").click();
		// hide() only hides the modal (bootstrap keeps the element around to reopen) — it
		// never leaves the page, so toBeHidden() is the correct check, not toHaveCount(0).
		await expect(page.locator(".side-panel-row-dialog")).toBeHidden();
		// the panel underneath is still open and usable
		await expect(page.locator(".side-panel")).toHaveClass(/is-open/);
	});

	test("the row's own \"open row\" button opens the same dialog", async ({ page }) => {
		await get_row(page).locator(".btn-open-row").click();

		await expect(page.locator(".side-panel-row-dialog")).toBeVisible();
		await expect(page.locator(".grid-row-open")).toHaveCount(0);
	});

	test("a normal document form's row still opens the native editor", async ({ page, desk }) => {
		// Guards against over-scoping the fix: a frm-bound grid must keep working exactly as
		// before — opening AND closing the native in-grid form, native-close included.
		await page.goto("/desk/contact/Test Contact");
		await page.waitForFunction(
			() => window.cur_frm && cur_frm.doc.name === "Test Contact" && cur_frm.get_field("phone_nos")
		);

		const table = page.locator('.frappe-control[data-fieldname="phone_nos"]');
		await table.locator(".rows .grid-row").first().locator(".btn-open-row").click();

		const row_form = page.locator(".grid-row-open");
		await expect(row_form).toBeVisible();

		await row_form.locator(".grid-form-heading").click();
		await expect(page.locator(".grid-row-open")).toHaveCount(0);
	});
});
