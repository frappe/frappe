import { test, expect } from "../support";

test.describe("Grid Configuration", () => {
	// restored in afterEach(), even on failure, so the shared Website Settings singleton isn't left mutated
	let saved_footer_items;

	test.beforeEach(async ({ page }) => {
		await page.goto("/desk/website-settings");
	});

	test.afterEach(async ({ admin, api }) => {
		await api.call("frappe.model.utils.user_settings.save", {
			doctype: "Website Settings",
			user_settings: { GridView: null },
		});

		if (!saved_footer_items) return;
		const footer_items_to_restore = saved_footer_items;
		saved_footer_items = undefined;

		await admin.update_doc("Website Settings", "Website Settings", {
			footer_items: footer_items_to_restore,
		});
	});

	test("Set user wise grid settings", async ({ page }) => {
		await page.getByRole("tab", { name: "Navbar", exact: true }).click();
		const table = page.locator('.frappe-control[data-fieldname="top_bar_items"]');
		await table.locator(".icon-sm").click();
		const modal = page.locator('.frappe-control[data-fieldname="fields_html"]');
		await modal.locator(".add-new-fields").click();
		await page.locator('[type="checkbox"][data-unit="right"]').check();
		await page.getByRole("button", { name: "Add", exact: true }).click();
		const column_width = page.locator(
			'.form-control.column-width[data-fieldname="parent_label"]'
		);
		await column_width.fill("1");
		await column_width.dispatchEvent("change");
		await page.getByRole("button", { name: "Update", exact: true }).click();
		await expect(page.locator('[title="Align Right"]').first()).toBeVisible();
	});

	test("Select All rechecks columns unchecked in the column selector", async ({ page }) => {
		await page.getByRole("tab", { name: "Navbar", exact: true }).click();
		const table = page.locator('.frappe-control[data-fieldname="top_bar_items"]');
		await table.locator(".icon-sm").click();
		const modal = page.locator('.frappe-control[data-fieldname="fields_html"]');
		await modal.locator(".add-new-fields").click();

		const dialog = page.locator(".modal.show", { hasText: "Select Fields" });
		const checkbox = dialog.locator('.unit-checkbox input[type="checkbox"]:checked').first();
		const fieldname = await checkbox.getAttribute("data-unit");
		await checkbox.uncheck();
		await dialog.getByRole("button", { name: "Select All", exact: true }).click();

		await expect(dialog.locator(`[type="checkbox"][data-unit="${fieldname}"]`)).toBeChecked();
	});

	test("Reset to default restores the default columns without a reload", async ({ page }) => {
		await page.getByRole("tab", { name: "Navbar", exact: true }).click();
		await page.evaluate(() => {
			cur_frm.add_child("top_bar_items", { label: "Home" });
			cur_frm.refresh_field("top_bar_items");
		});
		const table = page.locator('.frappe-control[data-fieldname="top_bar_items"]');
		const label_column = table.locator(
			'.grid-heading-row .grid-static-col[data-fieldname="label"]'
		);
		const sticky_label = table.locator('.sticky-grid-col[data-fieldname="label"]');
		const label_width = async () => Math.round((await label_column.boundingBox()).width);
		const default_width = await label_width();

		const handle = await label_column.locator(".grid-col-resize-handle").boundingBox();
		await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
		await page.mouse.down();
		await page.mouse.move(handle.x + 150, handle.y + handle.height / 2);
		await page.mouse.up();
		await expect.poll(label_width).toBeGreaterThan(default_width);

		await table.locator(".icon-sm").click();
		await page.locator('.sticky-column[data-fieldname="label"]').check();
		await page.locator(".add-new-fields").click();
		await page.locator('[type="checkbox"][data-unit="right"]').check();
		await page.getByRole("button", { name: "Add", exact: true }).click();
		await page.getByRole("button", { name: "Update", exact: true }).click();
		await expect(sticky_label).toHaveCount(2);

		await table.locator(".icon-sm").click();
		await page.getByRole("button", { name: "Reset to default", exact: true }).click();

		await expect(sticky_label).toHaveCount(0);
		await expect(table.locator('.grid-static-col[data-fieldname="right"]')).toHaveCount(0);
		await expect.poll(label_width).toBe(default_width);
	});

	test("Populates footer parent label options on page load", async ({ page, desk }) => {
		await page.getByRole("tab", { name: "Footer", exact: true }).click();
		saved_footer_items = await page.evaluate(() => {
			const saved = (cur_frm.doc.footer_items || []).map((row) => ({
				label: row.label,
				url: row.url,
				parent_label: row.parent_label,
				right: row.right,
				open_in_new_tab: row.open_in_new_tab,
			}));

			cur_frm.clear_table("footer_items");
			cur_frm.add_child("footer_items", { label: "Products" });
			cur_frm.add_child("footer_items", { label: "Phones" });
			cur_frm.refresh_field("footer_items");
			return saved;
		});
		await desk.save();

		await page.reload();
		await page.getByRole("tab", { name: "Footer", exact: true }).click();

		const get_parent_label_options = () =>
			page.evaluate(
				() =>
					cur_frm
						.get_field("footer_items")
						.grid.docfields.find((df) => df.fieldname === "parent_label").options
			);
		await expect.poll(get_parent_label_options).toContain("Products");
		await expect.poll(get_parent_label_options).toContain("Phones");
	});
});
