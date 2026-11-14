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

function tab(page, name) {
	return page.locator(EDITOR).getByRole("radio", { name, exact: true });
}

/** Add a Link row from the Add menu; the editor selects it. */
async function add_link(page, url, label) {
	await page.locator(`${EDITOR} [data-add]`).click();
	await page.getByRole("menuitem", { name: "Link", exact: true }).click();
	await page.locator(`${EDITOR} [data-field="url"]`).locator("visible=true").first().fill(url);
	await page
		.locator(`${EDITOR} [data-field="label"]`)
		.locator("visible=true")
		.first()
		.fill(label);
	await page.locator(`${EDITOR} [data-add-row]`).click();
	await expect(page.locator(`${EDITOR} [data-editor-pane]`).first()).toContainText(label);
}

function row_named(page, label) {
	return page.locator(`${EDITOR} [data-editor-list] li`).filter({ hasText: label });
}

/** Undo what a test stored at this level, so the next one starts from the default. */
async function reset_and_save(page) {
	await open_editor(page);
	await page.locator(`${EDITOR} [data-reset]`).click();
	await page.locator(`${EDITOR} [data-save]`).click();
	await expect(page.locator(EDITOR)).toHaveCount(0);
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
		// The hide is unsaved, so Reload asks before it drops it.
		await page.getByRole("button", { name: "Discard and reload" }).click();

		await expect(page.locator(`${EDITOR} [data-save-error]`)).toHaveCount(0);
		await expect(row(page, first)).toHaveCount(0);
		await expect(row(page, second)).toBeVisible();

		await page.locator(`${EDITOR} [data-reset]`).click();
		await page.locator(`${EDITOR} [data-save]`).click();
		await expect(page.locator(EDITOR)).toHaveCount(0);
		await other.close();
	});
	test("adds a link row, saves it, and keeps it on reopening", async ({ page }) => {
		await open_editor(page);
		await add_link(page, "/apps/todo", "My todos");
		await expect(row_named(page, "My todos")).toContainText("Added");
		await expect(page.locator(`${EDITOR} [data-save]`)).toBeEnabled();

		await page.locator(`${EDITOR} [data-save]`).click();
		await expect(page.locator(EDITOR)).toHaveCount(0);

		await open_editor(page);
		await expect(row_named(page, "My todos")).toBeVisible();
		await reset_and_save(page);

		await open_editor(page);
		await expect(row_named(page, "My todos")).toHaveCount(0);
	});

	test("deletes only a row the person added", async ({ page }) => {
		await open_editor(page);
		const [first] = await row_keys(page);
		await row(page, first).click();
		await expect(page.locator(`${EDITOR} [data-delete]`)).toHaveCount(0);

		await add_link(page, "/apps/todo", "Scratch");
		await page.locator(`${EDITOR} [data-delete]`).click();
		await expect(row_named(page, "Scratch")).toHaveCount(0);
		// Nothing is left to save: the draft is the opened one again.
		await expect(page.locator(`${EDITOR} [data-save]`)).toBeDisabled();
	});

	test("gives a row a sidebar, moves a row into it, and removes the sidebar", async ({
		page,
	}) => {
		await open_editor(page);
		await expect(tab(page, "Sidebar")).toHaveCount(0);

		await add_link(page, "/apps/todo", "Home base");
		await page.locator(`${EDITOR} [data-give-sidebar]`).click();
		await expect(tab(page, "Sidebar")).toBeVisible();
		await expect(page.locator(`${EDITOR} [data-editor-list] li`)).toHaveCount(1);

		await tab(page, "Rail").click();
		await add_link(page, "/apps/todo", "Mover");
		await page.locator(`${EDITOR} [data-move-to]`).click();
		await page.getByRole("menuitem", { name: "Home base", exact: true }).click();
		// The moved row shows in the sidebar's list, selected, and the rail no longer lists it.
		await expect(page.locator(`${EDITOR} [data-editor-list] li`)).toHaveCount(2);
		await expect(row_named(page, "Mover")).toBeVisible();
		await expect(page.locator(`${EDITOR} [data-editor-pane]`).first()).toContainText("Mover");
		await tab(page, "Rail").click();
		await expect(row_named(page, "Mover")).toHaveCount(0);

		// "Home base" cannot move into the sidebar it opens, and it has no other to go to.
		await row_named(page, "Home base").click();
		await expect(page.locator(`${EDITOR} [data-move-to]`)).toHaveCount(0);

		await page.locator(`${EDITOR} [data-remove-sidebar]`).click();
		await expect(tab(page, "Sidebar")).toHaveCount(0);
	});

	test("saves an own sidebar, keeps it on reopening, and drops it with its last row", async ({
		page,
	}) => {
		await open_editor(page);
		await add_link(page, "/apps/todo", "Home base");
		await page.locator(`${EDITOR} [data-give-sidebar]`).click();
		await page.locator(`${EDITOR} [data-save]`).click();
		await expect(page.locator(EDITOR)).toHaveCount(0);

		await open_editor(page);
		await tab(page, "Sidebar").click();
		await expect(page.locator(`${EDITOR} [data-editor-list] li`)).toHaveCount(1);
		await page.locator(`${EDITOR} [data-editor-list] li`).first().click();
		await page.locator(`${EDITOR} [data-delete]`).click();
		// The sidebar goes with its last row, and Home base is a plain row again.
		await expect(tab(page, "Sidebar")).toHaveCount(0);
		await row_named(page, "Home base").click();
		await expect(page.locator(`${EDITOR} [data-give-sidebar]`)).toBeVisible();
		await expect(page.locator(`${EDITOR} [data-remove-sidebar]`)).toHaveCount(0);

		await page.locator(`${EDITOR} [data-revert]`).click();
		await page.locator(EDITOR).getByRole("button", { name: "Cancel" }).click();
		await reset_and_save(page);
	});

	test("drags a row onto the other tab and drops it before a row there", async ({ page }) => {
		await open_editor(page);
		await add_link(page, "/apps/todo", "Home base");
		await page.locator(`${EDITOR} [data-give-sidebar]`).click();
		await tab(page, "Rail").click();
		await add_link(page, "/apps/todo", "Dragged");

		await row_named(page, "Dragged").hover();
		const from = await row_named(page, "Dragged").boundingBox();
		const to = await tab(page, "Sidebar").boundingBox();
		await page.mouse.move(from.x + 40, from.y + from.height / 2);
		await page.mouse.down();
		await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, { steps: 10 });
		await page.mouse.move(to.x + to.width / 2 + 2, to.y + to.height / 2, { steps: 2 });
		// Hovering the tab for 500 ms switches to it.
		await expect(row_named(page, "Dragged")).toHaveCount(0);
		const target = await row_named(page, "Home base").boundingBox();
		await page.mouse.move(target.x + 60, target.y + 4, { steps: 8 });
		await page.mouse.move(target.x + 62, target.y + 5, { steps: 2 });
		await page.mouse.up();

		await expect(page.locator(`${EDITOR} [data-editor-list] li`)).toHaveCount(2);
		await expect(page.locator(`${EDITOR} [data-editor-pane]`).first()).toContainText(
			"Dragged"
		);
		await expect(page.locator(`${EDITOR} [data-editor-list] li`).first()).toContainText(
			"Dragged"
		);
	});
});
