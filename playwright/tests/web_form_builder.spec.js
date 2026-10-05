import { test, expect } from "../support";
import {
	CANVAS,
	DOCTYPE_PAGE,
	PAGE,
	ROUTE,
	SINGLE_PAGE_FIELDS,
	SPLITTABLE_FIELDS,
	WEB_FORM_PAGE,
	expect_web_form_fields,
	fill_new_web_form,
	open_builder,
	seed_web_form,
} from "../support/web_form";

const ACTIVE_PAGE = `${CANVAS} .tab-content.active`;

const page_tabs = (page) => page.locator(`${CANVAS} .tab-header .tabs .tab`);

const canvas_field = (page, fieldname) =>
	page.locator(`${ACTIVE_PAGE} [data-fieldname='${fieldname}']`);

const first_column = (page, scope = ACTIVE_PAGE) =>
	page.locator(`${scope} .section-columns-container`).first().locator(".column").first();

const page_status = (page) => page.locator(`${PAGE} [data-testid="page-status"]`);

async function page_labels_should_be(page, labels) {
	await expect(page_tabs(page)).toHaveText(labels, { useInnerText: true });
}

async function move_second_section_to_new_page(page) {
	const section = page.locator(`${ACTIVE_PAGE} .form-section-container`).nth(1);
	await section.click({ position: { x: 15, y: 10 } });
	await section.locator(".dropdown-btn").first().click();
	await page
		.locator(".dropdown-options:visible .dropdown-item", {
			hasText: "Move sections to new page",
		})
		.first()
		.click();
}

async function open_add_field_picker(page) {
	await first_column(page).locator(".add-new-field-btn button").click();
}

async function pick_field(page, fieldname) {
	const search = page.locator(".combo-box-options:visible .search-box > input");
	await search.pressSequentially(fieldname);
	await search.press("Enter");
}

async function rename_first_section(page) {
	const label = page
		.locator(`${PAGE} ${ACTIVE_PAGE} .form-section-container`)
		.first()
		.locator("div[title='Double click to edit label']")
		.first();
	await label.dblclick();
	await label.locator("input").fill("Contact Details");
}

test.describe("Web Form Builder", () => {
	test("Adds Copy embed code once on the first save", async ({ page, desk }) => {
		await fill_new_web_form(desk, "Embed Note New");

		await desk.save();

		// the saved name routes to a second page, so scope to the Web Form one
		await expect(
			page.locator(`${WEB_FORM_PAGE} .user-action-link`, { hasText: "Copy embed code" })
		).toHaveCount(1);

		await expect(page.locator(`${WEB_FORM_PAGE} .user-action-row:empty`)).toHaveCount(0);
	});

	test("Adds page two to a form that has only page one", async ({ page, desk, api }) => {
		await seed_web_form(api, SINGLE_PAGE_FIELDS);
		await open_builder(page);

		await expect(page_tabs(page)).toHaveCount(1);
		await expect(page_tabs(page)).toContainText("Page 1");
		const first_tab = page.locator(`${CANVAS} .tab-header .tab`).first();
		await first_tab.hover();
		await expect(first_tab.locator(".remove-tab-btn")).toHaveCount(0);

		const new_tab_button = page.locator(`${CANVAS} .tab-header .tab-actions .new-tab-btn`);
		await expect(new_tab_button).toBeVisible();
		await new_tab_button.click();

		await expect(page_tabs(page)).toHaveCount(2);
		await expect(page_tabs(page).last()).toContainText("Page 2");

		// a page needs a field, or get_updated_fields() prunes its empty section away
		await first_column(page).locator(".empty-column .add-field-btn").click();
		await pick_field(page, "content");

		await desk.save();

		await expect_web_form_fields(page, (fields) => {
			const page_breaks = fields.filter((f) => f.fieldtype === "Page Break");
			expect(page_breaks.length, "one break for two pages").toBe(1);
			const break_idx = fields.findIndex((f) => f.fieldtype === "Page Break");
			const content_idx = fields.findIndex((f) => f.fieldname === "content");
			expect(content_idx, "content sits on page two").toBeGreaterThan(break_idx);
		});
	});

	test("Renumbers the pages after a page is inserted or deleted", async ({
		page,
		desk,
		api,
	}) => {
		await seed_web_form(api, SPLITTABLE_FIELDS);
		await open_builder(page);

		await move_second_section_to_new_page(page);
		await page_labels_should_be(page, ["Page 1", "Page 2", "Page 3"]);
		await expect(canvas_field(page, "public")).not.toHaveCount(0);

		const second_tab = page_tabs(page).nth(1);
		await second_tab.hover();
		await second_tab.locator(".remove-tab-btn").click();
		await desk.click_modal_primary_button("Delete page");

		await page_labels_should_be(page, ["Page 1", "Page 2"]);
		await expect(canvas_field(page, "public")).not.toHaveCount(0);
	});

	test("Stops Move sections to new page at the page limit", async ({ page, api }) => {
		await seed_web_form(api, SPLITTABLE_FIELDS);
		await open_builder(page);

		const tab_header = page.locator(`${CANVAS} .tab-header`);
		for (let i = 0; i < 8; i++) {
			await tab_header.hover();
			await tab_header.locator(".tab-actions .new-tab-btn").click();
		}
		await expect(page_tabs(page)).toHaveCount(10);
		await expect(page_tabs(page).last()).toContainText("Page 10");

		await page_tabs(page).first().click();
		await move_second_section_to_new_page(page);

		await expect(page.locator(".msgprint-dialog:visible .modal-title")).toContainText(
			"Too Many Pages"
		);
		await expect(page.locator(".msgprint")).toContainText(
			"There can be only 9 Page Break fields"
		);
		await expect(page_tabs(page)).toHaveCount(10);
	});

	test("Stops a tenth Page Break added from the fields grid", async ({ page, desk, api }) => {
		const nine_breaks = Array.from({ length: 9 }, () => ({ fieldtype: "Page Break" }));
		await seed_web_form(api, [...SINGLE_PAGE_FIELDS, ...nine_breaks]);

		await page.goto(`/desk/web-form/${ROUTE}`);
		await page.getByRole("tab", { name: "Settings", exact: true }).click();
		await desk.click_form_section("Fields");

		const grid = page.locator('[data-fieldname="web_form_fields"]');
		await grid.locator("button.grid-add-row").click();
		const new_row = grid.locator(".grid-body .grid-row").last();
		await new_row.locator('[data-fieldname="fieldtype"]').click();
		await new_row.locator('[data-fieldname="fieldtype"] select').selectOption("Page Break");

		await expect(page.locator(".msgprint-dialog:visible .modal-title")).toContainText(
			"Too Many Pages"
		);
	});

	test("Lays the stored rows out as pages", async ({ page, api }) => {
		await seed_web_form(api);
		await open_builder(page);

		await expect(page_tabs(page)).toHaveCount(2);
		await expect(page_tabs(page).first()).toContainText("Page 1");
		await expect(canvas_field(page, "title")).not.toHaveCount(0);
		await expect(canvas_field(page, "content")).toHaveCount(0);
	});

	test("Does not dirty the form by rendering", async ({ page, api }) => {
		await seed_web_form(api);
		await open_builder(page);

		await expect(page_status(page)).not.toContainText("Not Saved");
	});

	test("Writes the pages and a section label back without a Page Break for page one", async ({
		page,
		desk,
		api,
	}) => {
		await seed_web_form(api);
		await open_builder(page);

		await rename_first_section(page);

		await desk.save();

		await expect_web_form_fields(page, (fields) => {
			const page_breaks = fields.filter((f) => f.fieldtype === "Page Break");
			expect(page_breaks.length, "page break rows for two pages").toBe(1);
			expect([null, ""], "page break label").toContain(page_breaks[0].label ?? null);

			const section = fields.find((f) => f.fieldtype === "Section Break" && f.label);
			expect(section, "labelled section break row").toBeTruthy();
			expect(section.label).toBe("Contact Details");
			expect([null, ""], "section break fieldname").toContain(section.fieldname ?? null);
		});
	});

	test("Offers the source doctype's own fields, not fieldtypes", async ({ page, desk, api }) => {
		await seed_web_form(api);
		await open_builder(page);

		await open_add_field_picker(page);

		const options = page.locator(".combo-box-options:visible .combo-box-option");
		await expect(options).not.toHaveCount(0);
		await expect(options.filter({ hasText: /Title/ })).toHaveCount(0);
		await pick_field(page, "public");

		await expect(canvas_field(page, "public")).not.toHaveCount(0);

		await desk.save();

		await expect_web_form_fields(page, (fields) => {
			const placed = fields.filter((f) => f.fieldname === "public");
			expect(placed.length, "public appears once").toBe(1);
			expect(placed[0].fieldtype).toBe("Check");
		});
	});

	test("Repoints the add-field picker when the DocType changes", async ({ page, desk, api }) => {
		await seed_web_form(api, SINGLE_PAGE_FIELDS);
		await page.goto(`/desk/web-form/${ROUTE}`);
		await expect(page.locator(CANVAS)).toBeAttached();

		await desk.fill_field("doc_type", "ToDo", "Link");

		await page.getByRole("tab", { name: "Form", exact: true }).click();
		await open_add_field_picker(page);

		const options = page.locator(".combo-box-options:visible");
		await expect(options).toContainText("Priority");
		await expect(options).not.toContainText("Content");
	});

	test("Picks up rows removed from the Settings tab", async ({ page, desk, api }) => {
		await seed_web_form(api);
		await open_builder(page);

		await expect(canvas_field(page, "title")).not.toHaveCount(0);

		// the grid sits in the collapsed Fields section on Settings
		await page.getByRole("tab", { name: "Settings", exact: true }).click();
		await desk.click_form_section("Fields");
		await page
			.locator('[data-fieldname="web_form_fields"] .grid-row', { hasText: /Title/ })
			.first()
			.locator(".grid-row-check")
			.click();
		await page
			.locator('[data-fieldname="web_form_fields"] .grid-footer button', {
				hasText: "Delete",
			})
			.first()
			.click();

		// a tab switch syncs neither editor, the canvas re-reads the rows on save
		await desk.save();

		await page.getByRole("tab", { name: "Form", exact: true }).click();
		await expect(page.locator(`${CANVAS} .tab-content [data-fieldname='title']`)).toHaveCount(
			0
		);
	});

	// the popovers belong to the shared builder, but two builders can only be put on one
	// page from here, where a Web Form fixture is already seeded
	test("Shows the field picker in a builder opened without a page reload", async ({
		page,
		api,
	}) => {
		await seed_web_form(api);

		// the DocType builder goes first, so its container comes first in the DOM
		await page.goto("/desk/doctype/ToDo");
		await page.locator(DOCTYPE_PAGE).getByRole("tab", { name: "Form", exact: true }).click();
		await expect(page.locator(`${DOCTYPE_PAGE} ${CANVAS}`)).toBeVisible();

		// set_route resolves before the form renders. Clicking a tab too early lands on the
		// DocType page, so wait for the Web Form to be on screen
		await page.evaluate((route) => frappe.set_route("Form", "Web Form", route), ROUTE);
		await expect.poll(() => page.evaluate(() => cur_frm.doc.name)).toBe(ROUTE);
		await page.locator(WEB_FORM_PAGE).getByRole("tab", { name: "Form", exact: true }).click();
		await expect(page.locator(`${WEB_FORM_PAGE} ${CANVAS}`)).toBeVisible();

		await expect(page.locator(CANVAS)).toHaveCount(2);
		await expect(page.locator(".autocomplete-area")).toHaveCount(2);

		await first_column(page, `${WEB_FORM_PAGE} ${ACTIVE_PAGE}`)
			.locator(".add-new-field-btn button")
			.click();

		await expect(page.locator(".combo-box-options:visible")).not.toHaveCount(0);
	});

	test("Locks the canvas on a standard Web Form outside developer mode", async ({ page }) => {
		// edit-profile ships with Frappe as a standard form, and CI runs without developer mode
		await open_builder(page, "edit-profile");

		const fields = page.locator(`${ACTIVE_PAGE} .field`);
		await expect(fields).not.toHaveCount(0);

		await expect(page.locator(`${CANVAS} .add-new-field-btn`)).toHaveCount(0);

		// and a label cannot be renamed: the double click opens no input. A field's label, as
		// the lock hides an unlabelled section's
		await fields.locator("div[title='Double click to edit label']").first().dblclick();
		await expect(page.locator(`${CANVAS} input.input-text`)).toHaveCount(0);
	});

	test("Hides the form footer on the builder tab", async ({ page, api }) => {
		await seed_web_form(api);
		await open_builder(page);

		await expect(page.locator(`${PAGE} .form-footer`)).toBeHidden();

		await page.locator(PAGE).getByRole("tab", { name: "Settings", exact: true }).click();

		await page.locator(`${PAGE} .form-footer`).scrollIntoViewIfNeeded();
		await expect(page.locator(`${PAGE} .form-footer`)).toBeVisible();
	});

	test("Keeps the sidebar hidden on the builder tab across a save", async ({
		page,
		desk,
		api,
	}) => {
		await seed_web_form(api);
		await open_builder(page);

		await expect(page.locator(`${PAGE} .layout-side-section`)).toBeHidden();

		// dirty the canvas, or the save is a no-op and never rebuilds the sidebar
		await rename_first_section(page);
		await desk.save();

		await expect(page.locator(`${PAGE} .layout-side-section`)).toBeHidden();

		await page.locator(PAGE).getByRole("tab", { name: "Settings", exact: true }).click();
		await expect(page.locator(`${PAGE} .layout-side-section`)).toBeVisible();
	});

	test("Shows the sidebar after a save on the Settings tab", async ({ page, desk, api }) => {
		await seed_web_form(api);
		await page.goto(`/desk/web-form/${ROUTE}`);
		await page.locator(PAGE).getByRole("tab", { name: "Settings", exact: true }).click();
		await expect(page.locator(`${PAGE} .layout-side-section`)).toBeVisible();

		// any change will do, and this one sits in the always-open Access Control section
		await page.locator(`${PAGE} input[data-fieldname="anonymous"]`).check();
		await desk.save();
		await expect(page_status(page)).not.toContainText("Not Saved");

		await expect(page.locator(`${PAGE} .layout-side-section`)).toBeVisible();
	});

	test("Leaves the sidebar hidden on an unsaved form", async ({ page }) => {
		await page.goto("/desk/web-form/new");
		await expect(page.locator(`${PAGE} .layout-side-section`)).toBeHidden();

		// move onto the builder tab and back, the path that asks for the sidebar. An inline
		// display here would outrank Desk and leave an empty shell
		await page.locator(PAGE).getByRole("tab", { name: "Form", exact: true }).click();
		await page.locator(PAGE).getByRole("tab", { name: "Settings", exact: true }).click();
		await expect(page.locator(`${PAGE} .layout-side-section`)).toBeHidden();
	});
});
