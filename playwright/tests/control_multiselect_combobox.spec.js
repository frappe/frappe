import { test, expect, TEST_USER } from "../support";

const OTHER_USER = "multiselect_combobox@example.com";

// Table MultiSelect, MultiSelectPills and MultiSelect with the combobox setting on.
test.describe("Control MultiSelect (combobox)", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.set_value("System Settings", "System Settings", {
			enable_combobox_link_field: 1,
		});
		// a second user to pick; the search leaves out Administrator and Guest
		await admin.insert_doc(
			"User",
			{ email: OTHER_USER, first_name: "Multiselect", send_welcome_email: 0 },
			true
		);
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
		page.locator(`.frappe-control[data-fieldname=${fieldname}] .es-combobox`).first();
	const panel = (page) => page.locator(".es-combobox__panel[data-state='open']");
	const search = (page) => panel(page).locator(".es-combobox__input");
	const option = (page, text) =>
		panel(page).locator(".es-combobox__list [role='option']", { hasText: text }).first();
	const pills = (page, fieldname) =>
		page.locator(`.frappe-control[data-fieldname=${fieldname}] .es-combobox__pill:visible`);

	test("Table MultiSelect: ticks rows into child rows, keeps the panel open and removes a pill", async ({
		page,
		desk,
	}) => {
		await desk.new_form("User Group");
		const members = () =>
			page.evaluate(() => (cur_frm.doc.user_group_members || []).map((r) => r.user));

		await field(page, "user_group_members").click();
		await search(page).pressSequentially(OTHER_USER);
		await option(page, OTHER_USER).click();
		// a tick keeps the panel open
		await expect(panel(page)).toBeVisible();
		await expect(option(page, OTHER_USER)).toHaveAttribute("aria-selected", "true");
		await expect.poll(members).toEqual([OTHER_USER]);

		// Enter ticks the highlighted row
		await search(page).fill(TEST_USER);
		await expect(panel(page).locator(".es-combobox__list [role='option']")).toHaveCount(1);
		await search(page).press("Enter");
		await expect.poll(members).toEqual([OTHER_USER, TEST_USER]);
		await expect(pills(page, "user_group_members")).toHaveCount(2);
		await expect(panel(page).locator(".es-combobox__status")).toContainText("2 selected");

		// back to no search: the picked rows move under Selected
		await search(page).fill("");
		await expect(panel(page).locator(".es-menu__group-label").first()).toHaveText("Selected");
		await expect(
			panel(page).locator(".es-menu__group").first().locator("[aria-selected='true']")
		).toHaveCount(2);

		// the × on a pill removes its row; the panel stays open
		await pills(page, "user_group_members")
			.first()
			.locator(".es-combobox__pill-remove")
			.click();
		await expect.poll(members).toEqual([TEST_USER]);
		await expect(panel(page)).toBeVisible();
		await search(page).press("Escape");
		await expect(panel(page)).toHaveCount(0);
	});

	test("MultiSelectPills and MultiSelect: a list, a comma string, free text and Backspace", async ({
		page,
	}) => {
		// built in the page: get_data is a function, which can't be passed in
		const dialog = await page.evaluateHandle(() => {
			const d = new frappe.ui.Dialog({
				title: "Multi",
				fields: [
					// a plain first field, so no panel opens with the dialog
					{ fieldtype: "Data", fieldname: "note", label: "Note" },
					{
						fieldtype: "MultiSelectPills",
						fieldname: "pills",
						label: "Pills",
						options: ["Alpha", "Beta", "Gamma"],
					},
					{
						fieldtype: "MultiSelectPills",
						fieldname: "tags",
						label: "Tags",
						// ignores the typed text, like some app get_data functions
						get_data: () => ["Delta", "Echo"],
					},
					{
						fieldtype: "MultiSelect",
						fieldname: "colors",
						label: "Colors",
						options: ["Red", "Green"],
						default: "Green",
					},
					{
						fieldtype: "MultiSelect",
						fieldname: "emails",
						label: "Emails",
						ignore_validation: 1,
					},
				],
			});
			d.show();
			return d;
		});
		await page.waitForFunction((d) => d.display, dialog);
		const value_of = (fieldname) => dialog.evaluate((d, f) => d.get_value(f), fieldname);

		// MultiSelectPills: a list of values, in pick order
		await field(page, "pills").click();
		await option(page, "Beta").click();
		await option(page, "Alpha").click();
		await expect.poll(() => value_of("pills")).toEqual(["Beta", "Alpha"]);
		// Backspace in the empty search removes the last pill
		await search(page).press("Backspace");
		await expect.poll(() => value_of("pills")).toEqual(["Beta"]);
		await search(page).press("Escape");
		await expect(panel(page)).toHaveCount(0);

		// get_data rows are filtered by the typed text, and any typed text can be added
		await field(page, "tags").click();
		await search(page).pressSequentially("ech");
		await expect(panel(page).locator(".es-combobox__list [role='option']")).toHaveCount(1);
		await search(page).fill("Foxtrot");
		await expect(panel(page).locator(".es-combobox__footer")).toContainText('Use "Foxtrot"');
		await search(page).press("Enter");
		await expect.poll(() => value_of("tags")).toEqual(["Foxtrot"]);
		await search(page).press("Escape");

		// MultiSelect: the default shows under Selected, and the value is a comma string
		await expect(pills(page, "colors")).toHaveCount(1);
		await field(page, "colors").click();
		await expect(panel(page).locator(".es-menu__group-label").first()).toHaveText("Selected");
		await option(page, "Red").click();
		await expect.poll(() => value_of("colors")).toBe("Green, Red");
		await search(page).press("Escape");
		// as the classic control, a value outside the fixed list is refused
		await dialog.evaluate((d) => d.fields_dict.colors.set_value("Green, Purple"));
		await expect.poll(() => value_of("colors")).toBe("");

		// free text: "Use …" adds the typed text and clears the search
		await field(page, "emails").click();
		await search(page).pressSequentially("someone@example.com");
		await expect(panel(page).locator(".es-combobox__footer")).toContainText(
			'Use "someone@example.com"'
		);
		await search(page).press("Enter");
		await expect(search(page)).toHaveValue("");
		await expect(panel(page)).toBeVisible();
		await expect.poll(() => value_of("emails")).toBe("someone@example.com");
		await search(page).press("Escape");
	});
});
