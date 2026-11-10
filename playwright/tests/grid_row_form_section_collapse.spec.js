import { test, expect } from "../support";
import child_table_with_collapsible_section from "../fixtures/child_table_with_collapsible_section";
import doctype_with_collapsible_child_section from "../fixtures/doctype_with_collapsible_child_section";

const parent_doctype_name = doctype_with_collapsible_child_section.name;

test.describe("Grid Row Form Section Collapse", () => {
	let table, row_form, section, description;

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", child_table_with_collapsible_section, true);
		await admin.insert_doc("DocType", doctype_with_collapsible_child_section, true);
	});

	test.beforeEach(async ({ page, desk }) => {
		await desk.new_form(parent_doctype_name);
		await desk.fill_field("title", "Test Document");

		table = page.locator('.frappe-control[data-fieldname="items"]');
		await table.getByRole("button", { name: "Add row", exact: true }).click();
		await table.locator('[data-idx="1"] .btn-open-row').click();

		row_form = page.locator(".grid-row-open");
		// the row form focuses its first input once its opening animation is over
		await expect(row_form.locator(".form-area input").first()).toBeFocused();
		section = row_form.locator('.form-section[data-fieldname="details_section"]');
		description = row_form.locator('.frappe-control[data-fieldname="description"] textarea');
	});

	// `notes` depends on `description`, so it turns visible only once the row has
	// been refreshed — without waiting for it the assertions below race the refresh.
	const type_description = async () => {
		await description.pressSequentially("Hello");
		await description.blur();
		await expect(row_form.locator('.frappe-control[data-fieldname="notes"]')).toBeVisible();
	};

	test("collapses the section until the user opens it", async () => {
		await expect(section.locator(".section-body")).toHaveClass(/(^|\s)hide(\s|$)/);
	});

	test("keeps the section open while typing in a field inside it", async () => {
		await section.locator(".section-head").click();
		await expect(section.locator(".section-body")).not.toHaveClass(/(^|\s)hide(\s|$)/);

		await type_description();

		await expect(section.locator(".section-body")).not.toHaveClass(/(^|\s)hide(\s|$)/);
		await expect(description).toHaveValue("Hello");
	});

	test("keeps the section collapsed after the user closes it", async ({ page }) => {
		await section.locator(".section-head").click();
		await type_description();
		await section.locator(".section-head").click();
		await expect(section.locator(".section-body")).toHaveClass(/(^|\s)hide(\s|$)/);

		await page.evaluate(() => cur_frm.refresh_fields());

		await expect(section.locator(".section-body")).toHaveClass(/(^|\s)hide(\s|$)/);
	});

	test("collapses the section again when the row form is reopened", async ({ page }) => {
		await section.locator(".section-head").click();
		await expect(section.locator(".section-body")).not.toHaveClass(/(^|\s)hide(\s|$)/);

		await row_form.locator(".grid-collapse-row").click();
		await table.locator('[data-idx="1"] .btn-open-row').click();

		await expect(
			page
				.locator(".grid-row-open")
				.locator('.form-section[data-fieldname="details_section"] .section-body')
		).toHaveClass(/(^|\s)hide(\s|$)/);
	});
});
