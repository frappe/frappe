import { test, expect } from "../support";

const GS_GRID = '.frappe-control[data-fieldname="allowed_in_global_search"]';
const UPDATE_FIELDS =
	"/api/method/frappe.desk.doctype.global_search_settings.global_search_settings.update_global_search_fields";

async function ensure_first_priority_row(page) {
	if ((await page.locator(`${GS_GRID} .grid-body .grid-row`).count()) === 0) {
		await page.locator(`${GS_GRID} .grid-add-row`).click();
	}
	const row = page.locator(`${GS_GRID} .grid-body .grid-row[data-idx="1"]`);
	await expect(row).toBeAttached();
	return row;
}

async function activate_document_type_cell(row) {
	await row.locator('[data-fieldname="document_type"]').first().click();
	await expect(row.locator('[data-fieldname="document_type"] input').first()).toBeAttached();
}

async function select_document_type_link(page, row, label) {
	const input = row.locator('[data-fieldname="document_type"] input').first();
	await input.clear();
	await input.focus();
	await input.pressSequentially(label, { delay: 100 });
	await expect(input).toHaveAttribute("aria-owns", /\w+/);

	const dropdown = page.locator(`[id="${await input.getAttribute("aria-owns")}"]`);
	await expect(dropdown).toBeVisible();
	const option = dropdown
		.locator('[role="option"]')
		.filter({ has: page.getByText(label, { exact: true }) });
	await expect(option).toHaveCount(1);
	await option.scrollIntoViewIfNeeded();
	await option.click();

	await input.blur();
	await expect(input).toHaveValue(label);
}

test.describe("Global Search Settings — configure search fields", () => {
	test.beforeEach(async ({ page, desk }) => {
		await desk.login("Administrator");
		await page.goto("/desk/global-search-settings");
		await expect(page.locator("body")).toHaveAttribute("data-ajax-state", "complete");
		await expect(page.locator(GS_GRID)).toBeAttached();
	});

	test("shows a message when Configure is clicked without Document Type", async ({ page }) => {
		await page.locator(GS_GRID).locator(".grid-add-row").click();
		await page
			.locator(`${GS_GRID} .grid-body .grid-row`)
			.last()
			.locator('[data-fieldname="configure"] button')
			.click();
		await expect(page.locator(".msgprint:visible")).toContainText(
			"Please select Document Type first"
		);
	});

	test("opens configure dialog with MultiCheck field options and filter search", async ({
		page,
		desk,
	}) => {
		const row = await ensure_first_priority_row(page);
		await activate_document_type_cell(row);
		await select_document_type_link(page, row, "ToDo");

		await row.locator('[data-fieldname="configure"] button').click();

		const dialog = desk.get_open_dialog();
		await expect(dialog.locator(".modal-title")).toContainText("Configure search fields");
		await expect(dialog).toContainText("ToDo");
		await expect(
			dialog.locator('.checkbox-options input[type="checkbox"][data-unit="name"]')
		).toBeAttached();

		// the modal takes focus when it finishes opening, which would swallow a keyup
		await page.waitForFunction(() => cur_dialog?.display);
		const search = dialog.locator('[data-element="search"]');
		const visible_options = dialog.locator(".checkbox-options .unit-checkbox:visible");
		await search.clear();
		await search.pressSequentially("xyz-nonmatching-global-search-filter-12345");
		await expect(visible_options).toHaveCount(0);
		await search.press("ControlOrMeta+a");
		await search.press("Backspace");
		await expect(visible_options).not.toHaveCount(0);

		await desk.hide_dialog();
	});

	test("saves selected fields and shows success toast", async ({ page, desk }) => {
		const row = await ensure_first_priority_row(page);
		await activate_document_type_cell(row);
		// Must not be a Core module DocType — API rejects those (no toast; server error).
		await select_document_type_link(page, row, "ToDo");

		await row.locator('[data-fieldname="configure"] button').click();

		const dialog = desk.get_open_dialog();
		await expect(
			dialog.locator('.checkbox-options input[type="checkbox"][data-unit="name"]')
		).toBeAttached();

		const updated = page.waitForResponse(
			(res) => res.request().method() === "POST" && res.url().includes(UPDATE_FIELDS)
		);
		await dialog
			.locator(".modal-footer .standard-actions .btn-modal-primary", { hasText: "Save" })
			.click();

		const response = await updated;
		const body = await response.json();
		expect(response.status()).toBe(200);
		expect(body.exc, JSON.stringify(body)).toBeUndefined();
		expect(body.message?.success).toBe(true);

		await expect(page.locator(".es-toast .es-toast__message")).toContainText(
			"Search fields updated.",
			{ timeout: 25000 }
		);
	});
});
