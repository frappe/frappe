import { test, expect } from "../support";

const EDITOR = "[data-navigation-editor]";

async function open_editor(page) {
	await page.goto("/apps/desk/todo#customize/rail");
	await expect(page.locator(`${EDITOR} [data-editor-list] li`).first()).toBeVisible();
}

function row(page, key) {
	return page.locator(`${EDITOR} [data-editor-list] li[data-key="${key}"]`);
}

async function row_keys(page) {
	return page
		.locator(`${EDITOR} [data-editor-list] li`)
		.evaluateAll((rows) => rows.map((row) => row.dataset.key));
}

async function hide_and_save(page, key) {
	await row(page, key).click();
	await page
		.locator(`${EDITOR} [data-row-actions]`)
		.getByRole("button", { name: "Hide" })
		.click();
	await page.locator(`${EDITOR} [data-save]`).click();
}

test.describe("Desk v2 navigation editor", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
	});

	test.afterAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	test("hides a row, keeps it under Show hidden, shows it again, and resets to default", async ({
		page,
	}) => {
		await open_editor(page);
		const [first] = await row_keys(page);

		await hide_and_save(page, first);
		await expect(page.locator(EDITOR)).toHaveCount(0);

		await open_editor(page);
		await expect(row(page, first)).toHaveCount(0);
		await page.locator(`${EDITOR}`).getByLabel("Show hidden").check();
		await expect(row(page, first)).toContainText("Hidden");

		await row(page, first).click();
		await page
			.locator(`${EDITOR} [data-row-actions]`)
			.getByRole("button", { name: "Show" })
			.click();
		await page.locator(`${EDITOR} [data-save]`).click();
		await expect(page.locator(EDITOR)).toHaveCount(0);

		// Showing it again leaves nothing stored, so there is nothing to reset.
		await open_editor(page);
		await expect(page.locator(`${EDITOR} [data-reset]`)).toHaveCount(0);
		await expect(row(page, first)).toBeVisible();

		// What this level stored is undone by one Reset, which Save then commits.
		await hide_and_save(page, first);
		await expect(page.locator(EDITOR)).toHaveCount(0);
		await open_editor(page);
		await page.locator(`${EDITOR} [data-reset]`).click();
		await page.locator(`${EDITOR} [data-save]`).click();
		await expect(page.locator(EDITOR)).toHaveCount(0);

		await open_editor(page);
		await expect(page.locator(`${EDITOR} [data-reset]`)).toHaveCount(0);
		await expect(row(page, first)).toBeVisible();
	});

	test("a save in another tab makes this one stale, and Reload takes the new rows", async ({
		page,
	}) => {
		await open_editor(page);
		const [first, second] = await row_keys(page);

		const other = await page.context().newPage();
		await open_editor(other);
		await hide_and_save(other, first);
		await expect(other.locator(EDITOR)).toHaveCount(0);

		await hide_and_save(page, second);
		await expect(page.locator(`${EDITOR} [data-save-error]`)).toBeVisible();
		await page
			.locator(`${EDITOR} [data-save-error]`)
			.getByRole("button", { name: "Reload" })
			.click();

		await expect(page.locator(`${EDITOR} [data-save-error]`)).toHaveCount(0);
		await expect(row(page, first)).toHaveCount(0);
		await expect(row(page, second)).toBeVisible();

		await page.locator(`${EDITOR} [data-reset]`).click();
		await page.locator(`${EDITOR} [data-save]`).click();
		await expect(page.locator(EDITOR)).toHaveCount(0);
		await other.close();
	});
});
