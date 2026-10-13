import { test, expect, use_shared_page } from "../support";
import form_builder_doctype from "../fixtures/form_builder_doctype";

const doctype_name = form_builder_doctype.name;
const LABEL = "div[title='Double click to edit label']";

const first_section = (page) =>
	page.locator(".tab-content.active .form-section-container").first();
const first_column = (page) =>
	page
		.locator(".tab-content.active .section-columns-container")
		.first()
		.locator(".column")
		.first();
const first_field = (page) => first_column(page).locator(".field").first();
const last_field = (page) => first_column(page).locator(".field").last();
const label_text = (field) => field.locator(`${LABEL} span`).first();
const sidebar_checkbox = (page, label) =>
	page
		.locator(".sidebar-container .field label .label-area")
		.getByText(label, { exact: true })
		.first();
const sidebar_input = (page, fieldname) =>
	page.locator(`.sidebar-container .frappe-control[data-fieldname='${fieldname}'] input`);
const msgprint = (desk) => desk.get_open_dialog().locator(".msgprint");

async function open_form_builder(page) {
	await page.goto(`/desk/doctype/${doctype_name}`);
	await page.getByRole("tab", { name: "Form", exact: true }).click();
	await expect(page.locator(".form-builder-container")).toBeVisible();
}

async function edit_label(field) {
	await field.click();
	const label = field.locator(LABEL);
	await label.dblclick();
	return label.locator("input");
}

async function open_section_menu(page) {
	await first_section(page).click({ position: { x: 15, y: 10 } });
	await first_section(page).locator(".dropdown-btn").first().click();
	return page.locator(".dropdown-options:visible .dropdown-item");
}

async function add_new_field(page, fieldtype) {
	await first_column(page).locator(".add-new-field-btn button").click();
	const search = page.locator(".combo-box-options:visible .search-box > input");
	await search.pressSequentially(fieldtype);
	await search.press("Enter");
}

test.describe("Form Builder", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", form_builder_doctype, true);
		await admin.update_doc("DocType", doctype_name, { fields: form_builder_doctype.fields });
	});

	test("Open Form Builder for Web Form Doctype/Customize Form", async ({ page }) => {
		await page.goto("/desk/doctype/Web Form");
		await page.getByRole("tab", { name: "Form", exact: true }).click();
		await expect(page.locator(".form-builder-container")).toBeAttached();

		await page.goto("/desk/customize-form?doc_type=Web%20Form");
		await page.getByRole("tab", { name: "Form", exact: true }).click();
		await expect(page.locator(".form-builder-container")).toBeAttached();
	});

	test("Save without change, check form dirty", async ({ page, desk }) => {
		await open_form_builder(page);

		await desk.click_primary_button("Save");
		await expect(page.locator('.es-toast[data-type="warning"] .es-toast__message')).toHaveText(
			"No changes in document"
		);

		const label_input = await edit_label(first_field(page));
		await label_input.pressSequentially("Dirty");
		const page_status = page.locator('[data-testid="page-status"]:visible');
		await expect(page_status).toBeVisible();
		await expect(page_status).toContainText("Not Saved");
	});

	test("Check if Filters are applied to the link field", async ({ page, desk }) => {
		await open_form_builder(page);

		await page.locator("[data-fieldname='gender']").click();
		await page.locator('[data-fieldname="gender"] .field-actions button').first().click();

		await page.locator(".modal-body .clear-filters").click();
		await page.locator(".modal-body .filter-action-buttons .add-filter").click();

		const input = page.locator(
			".modal-body .filter-box .list_filter .filter-field .link-field input"
		);
		const dropdown = input.locator("xpath=..").getByRole("listbox");
		await input.focus();
		await expect(dropdown).toBeVisible();
		await input.pressSequentially("Male", { delay: 100 });
		await expect(dropdown.locator("[role='option']").first()).toContainText("Male");
		await input.press("Enter");
		await input.blur();

		await page.locator(".btn-modal-primary:visible").click();
		await expect(page.locator(".modal:visible")).toHaveCount(0);

		await desk.save();

		await expect
			.poll(() => page.evaluate(() => cur_frm.doc.fields[1]))
			.toMatchObject({
				fieldname: "gender",
				link_filters: '[["Gender","name","=","Male"]]',
			});
	});

	test("Add empty section and save", async ({ page, desk }) => {
		await open_form_builder(page);

		const sections = page.locator(".tab-content.active .form-section-container");
		const menu_items = await open_section_menu(page);
		await menu_items.first().click();
		await expect(sections).toHaveCount(2);

		await desk.click_primary_button("Save");
		await expect(sections).toHaveCount(1);
	});

	test("Add Table field and check if columns are rendered", async ({ page, desk }) => {
		await open_form_builder(page);

		await add_new_field(page, "table");

		await desk.click_primary_button("Save");

		await expect(msgprint(desk)).toContainText("Options is required");
		await desk.hide_dialog();

		await last_field(page).click();

		const options = sidebar_input(page, "options");
		await options.click();
		await options.clear();
		await options.pressSequentially("Web Form Field", { delay: 200 });
		await expect(options.locator("xpath=..").locator("[role='option']").first()).toContainText(
			"Web Form Field"
		);

		await last_field(page).click();

		const table_columns = last_field(page).locator(".table-controls .table-column");
		await expect(table_columns.getByText(/Field/).first()).toBeAttached();
		await expect(table_columns.getByText(/Fieldtype/).first()).toBeAttached();

		await sidebar_checkbox(page, "In List View").click();

		await desk.click_primary_button("Save");

		await expect(msgprint(desk)).toContainText("In List View");
		await desk.hide_dialog();

		await last_field(page).click();
		await sidebar_checkbox(page, "In List View").click();

		await sidebar_checkbox(page, "In Global Search").click();

		await desk.click_primary_button("Save");

		await expect(msgprint(desk)).toContainText("In Global Search");
	});

	// not important and was flaky on CI
	test.skip("Drag Field/Column/Section & Tab", async ({ page }) => {
		await open_form_builder(page);

		const first_tab = page.locator(".tab-header .tabs .tab").first();

		await first_tab.click();

		await first_tab.dragTo(page.locator(".tab-header .tabs .tab:nth-child(2)"), {
			targetPosition: { x: 10, y: 10 },
			force: true,
		});
		await expect(label_text(first_tab)).toHaveText("Tab 2");

		await first_tab.click();
		await page.locator(".sidebar-container .tab").first().click();

		await page
			.locator(".fields-container .field[title='Check']")
			.dragTo(first_field(page), { targetPosition: { x: 100, y: 10 } });
		await expect(first_column(page).locator(".field")).toHaveCount(3);

		const label_input = await edit_label(first_field(page));
		await label_input.pressSequentially("Test Check");
		await expect(label_text(first_field(page))).toHaveText("Test Check");

		await first_field(page).dragTo(first_column(page).locator(".field:nth-child(2)"), {
			targetPosition: { x: 100, y: 10 },
		});
		await expect(label_text(first_field(page))).toHaveText("Data");

		await first_column(page).click();
		await first_column(page)
			.locator(".column-actions")
			.dragTo(page.locator(".section-columns-container").first().locator(".column").last(), {
				targetPosition: { x: 100, y: 10 },
				force: true,
			});
		await expect(label_text(first_field(page))).toHaveText("Data 1");

		await first_section(page).click();
		await first_section(page)
			.locator(".section-header")
			.dragTo(page.locator(".form-section-container:nth-child(2)"), {
				targetPosition: { x: 100, y: 10 },
				force: true,
			});
		await expect(label_text(first_field(page))).toHaveText("Data 2");
	});

	test.describe(() => {
		const shared = use_shared_page();

		test("Add New Tab/Section/Column to Form", async () => {
			const { page } = shared;
			await open_form_builder(page);

			await page.locator(".tab-header").hover();
			await page.locator(".tab-header .tab-actions .new-tab-btn").click();
			await expect(page.locator(".tab-header .tabs .tab")).toHaveCount(3);

			let menu_items = await open_section_menu(page);
			await menu_items.first().click();
			await expect(page.locator(".tab-content.active .form-section-container")).toHaveCount(
				2
			);

			menu_items = await open_section_menu(page);
			await menu_items.last().click();
			await expect(first_section(page).locator(".column")).toHaveCount(2);
		});

		test("Remove Tab/Section/Column", async () => {
			const { page } = shared;

			let menu_items = await open_section_menu(page);
			await menu_items.last().click();
			await expect(first_section(page).locator(".column")).toHaveCount(1);

			menu_items = await open_section_menu(page);
			await menu_items.nth(1).click();
			await expect(page.locator(".tab-content.active .form-section-container")).toHaveCount(
				1
			);

			const last_tab = page.locator(".tab-header .tab").last();
			await last_tab.hover();
			await last_tab.locator(".remove-tab-btn").click();
			await expect(page.locator(".tab-header .tabs .tab")).toHaveCount(2);
		});
	});

	test("Update Title field Label to New Title through Customize Form", async ({
		page,
		desk,
	}) => {
		await open_form_builder(page);

		const label_input = await edit_label(first_field(page));
		await label_input.press("ControlOrMeta+a");
		await label_input.pressSequentially("New Title");

		await desk.save();

		await page.goto("/desk/form-builder-doctype/new");
		await expect(page.locator("[data-fieldname='data3'] .clearfix label")).toHaveText(
			"New Title"
		);
	});

	test("Validate Duplicate Name & reqd + hidden without default logic", async ({
		page,
		desk,
	}) => {
		await open_form_builder(page);

		await add_new_field(page, "data");

		await last_field(page).click();

		const fieldname = sidebar_input(page, "fieldname");
		await fieldname.click();
		await fieldname.clear();
		await fieldname.pressSequentially("data3");

		await desk.click_primary_button("Save");
		await expect(msgprint(desk)).toContainText("appears multiple times");
		await desk.hide_dialog();
		await last_field(page).click();
		await fieldname.clear();

		await sidebar_checkbox(page, "Mandatory").click();
		await sidebar_checkbox(page, "Hidden").click();

		await desk.click_primary_button("Save");

		await expect(msgprint(desk)).toContainText(
			"cannot be hidden and mandatory without any default value"
		);
	});

	test.skip("Undo/Redo", async ({ page }) => {
		await open_form_builder(page);

		await page.locator(".tab-header .tabs .tab").last().click();

		await first_field(page).dragTo(first_column(page).locator(".field:nth-child(2)"), {
			targetPosition: { x: 100, y: 10 },
		});
		await expect(label_text(first_field(page))).toHaveText("Check");

		await page.keyboard.press("Control+z");
		await expect(label_text(first_field(page))).toHaveText("Data");

		await page.keyboard.press("Control+Shift+z");
		await expect(label_text(first_field(page))).toHaveText("Check");
	});
});
