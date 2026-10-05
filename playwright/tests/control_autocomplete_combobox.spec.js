import { test, expect } from "../support";

// The Autocomplete field with the combobox setting on.
test.describe("Control Autocomplete (combobox)", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.set_value("System Settings", "System Settings", {
			enable_combobox_link_field: 1,
		});
	});

	test.afterAll(async ({ admin }) => {
		await admin.set_value("System Settings", "System Settings", {
			enable_combobox_link_field: 0,
		});
	});

	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();
	});

	const field = (page, fieldname) =>
		page.locator(`.modal.show .frappe-control[data-fieldname=${fieldname}] .es-combobox`);
	const panel = (page) => page.locator(".es-combobox__panel[data-state='open']");
	const search = (page) => panel(page).locator(".es-combobox__input");
	const value_of = (dialog, fieldname) => dialog.evaluate((d, f) => d.get_value(f), fieldname);

	test("keeps free text when it is allowed, and drops it when the list is the rule", async ({
		page,
		desk,
	}) => {
		const dialog = await desk.dialog({
			title: "Autocomplete",
			fields: [
				// a plain first field, so no panel opens with the dialog
				{ label: "Note", fieldname: "note", fieldtype: "Data" },
				{
					label: "Listed",
					fieldname: "listed",
					fieldtype: "Autocomplete",
					options: ["Option 1", "Option 2"],
				},
				{
					label: "Free",
					fieldname: "free",
					fieldtype: "Autocomplete",
					options: ["Option 1", "Option 2"],
					ignore_validation: 1,
				},
			],
		});

		// list only: a match is picked, and text matching nothing leaves the value alone
		await field(page, "listed").click();
		await search(page).pressSequentially("2");
		await search(page).press("Enter");
		await expect.poll(() => value_of(dialog, "listed")).toBe("Option 2");
		await field(page, "listed").click();
		await search(page).pressSequentially("zzz");
		await expect(panel(page).locator(".es-menu__empty")).toBeVisible();
		await page.locator(".modal.show .modal-title").click();
		await expect(panel(page)).toHaveCount(0);
		await expect.poll(() => value_of(dialog, "listed")).toBe("Option 2");

		// free text: the footer row offers it, and Enter commits it
		await field(page, "free").click();
		await search(page).pressSequentially("Custom");
		await expect(panel(page).locator(".es-combobox__footer [role='option']")).toContainText(
			'Use "Custom"'
		);
		await search(page).press("Enter");
		await expect(panel(page)).toHaveCount(0);
		await expect.poll(() => value_of(dialog, "free")).toBe("Custom");
	});
});
