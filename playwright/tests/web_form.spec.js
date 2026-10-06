import { test, expect } from "../support";

async function set_web_form_fields_without_fieldname(api, fields) {
	const { data } = await api.get_doc("Web Form", "note");
	data.web_form_fields = [...data.web_form_fields.filter((df) => df.fieldname), ...fields];
	await api.call("frappe.client.save", { doc: data });
}

async function set_web_form_field_default(api, fieldname, value) {
	const { data } = await api.get_doc("Web Form", "note");
	const field = data.web_form_fields.find((df) => df.fieldname === fieldname);
	await api.set_value("Web Form Field", field.name, { default: value });
}

// the profile forms append to a middle name on every run. Left to grow, the title wraps
// and the Not Saved badge that appears on blur moves Submit from under the pointer
async function reset_profile_names(admin) {
	const { data } = await admin.get_list(
		"User",
		["name"],
		[["middle_name", "like", "%_Test User%"]]
	);
	for (const user of data) {
		await admin.set_value("User", user.name, { middle_name: "" });
	}
}

async function open_settings(page, tab = "Settings") {
	await page.goto("/desk/web-form/note");
	await page.getByRole("tab", { name: tab, exact: true }).click();
}

async function submit_web_form(page) {
	const accepted = page.waitForResponse((res) =>
		res.request().postData()?.includes("web_form.accept")
	);
	await page.locator(".web-form-actions button", { hasText: "Save" }).first().click();
	await accepted;
}

async function open_last_list_row(page) {
	await page.goto("/note");
	await expect(page).toHaveURL(/\/note\/list/);
	await page.locator(".web-list-table tbody tr").last().click();
}

const first_breadcrumb = (page) =>
	page.locator(".breadcrumb-container .breadcrumb .breadcrumb-item").first().locator("a");

const list_header = (page, text) =>
	page.locator(".web-list-table thead th", { hasText: text }).first();

test.describe("Web Form", () => {
	test.describe.configure({ mode: "serial" });

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.prepare_webform_test");
		await reset_profile_names(admin);
	});

	test.afterAll(async ({ admin }) => {
		await reset_profile_names(admin);
	});

	test.beforeEach(async ({ desk }) => {
		await desk.login("Administrator");
	});

	test("Create Web Form", async ({ page, desk }) => {
		await page.goto("/desk/web-form/new");

		await desk.fill_field("title", "Note");
		await desk.fill_field("doc_type", "Note", "Link");
		await desk.fill_field("module", "Website", "Link");
		await desk.click_custom_action_button("Get Fields");
		await expect(page.locator('[data-fieldname="web_form_fields"] .grid-row')).not.toHaveCount(
			0
		);
		const saved = page.waitForResponse(
			(res) =>
				res.request().method() === "POST" &&
				res.url().includes("/api/method/frappe.desk.form.save.savedocs")
		);
		await desk.click_custom_action_button("Publish");
		await saved;

		await page.locator('.frappe-control[data-fieldname="route"]').scrollIntoViewIfNeeded();
		await expect(desk.get_field("route")).toHaveValue("note");

		const status = page.locator('[data-testid="page-status"]');
		await expect(status).toContainText("Published");
		await expect(status).toHaveAttribute("data-theme", "green");
	});

	test("Open Web Form", async ({ page, desk }) => {
		await page.goto("/note");
		await desk.fill_field("title", "Note 1");
		await submit_web_form(page);

		await expect(page).toHaveURL(/\/note\/new/);

		await desk.logout();
		await page.goto("/note");

		await expect(page).toHaveURL(/\/note\/new/);

		await desk.fill_field("title", "Guest Note 1");
		await submit_web_form(page);

		await expect(page).toHaveURL(/\/note\/new/);

		await page.goto("/note");
		await expect(page).toHaveURL(/\/note\/new/);
	});

	test("Login Required", async ({ page, desk }) => {
		await open_settings(page);
		await page.locator('input[data-fieldname="login_required"]').check();

		await desk.save();

		await page.goto("/note");

		await desk.logout();

		await page.goto("/note");
		await expect(
			page.getByText("You must be logged in to use this form.").first()
		).toBeVisible();
	});

	test("Show List", async ({ page, desk }) => {
		await open_settings(page);
		await desk.click_form_section("List Settings");
		await page.locator('input[data-fieldname="show_list"]').check();

		await desk.save();

		await page.goto("/note");
		await expect(page).toHaveURL(/\/note\/list/);
		await expect(page.locator(".web-list-table")).toBeVisible();
	});

	test("Show Custom List Title", async ({ page, desk }) => {
		await open_settings(page);

		await page
			.locator(".section-head", { hasText: "List Settings" })
			.first()
			.scrollIntoViewIfNeeded();

		await desk.fill_field("list_title", "Note List");
		await expect.poll(() => page.evaluate(() => cur_frm.doc.list_title)).toBe("Note List");

		await desk.save();

		await page.goto("/note");
		await expect(page).toHaveURL(/\/note\/list/);
		await expect(page.locator(".web-list-header h1")).toContainText("Note List");
	});

	test("Show Custom List Columns", async ({ page, desk }) => {
		await page.goto("/note");
		await expect(page).toHaveURL(/\/note\/list/);

		await expect(list_header(page, "Sr.")).toBeAttached();
		await expect(list_header(page, "Title")).toBeAttached();

		await open_settings(page);

		const add_row = page
			.locator('[data-fieldname="list_columns"] .grid-footer button', { hasText: "Add row" })
			.first();
		const grid_rows = page.locator('[data-fieldname="list_columns"] .grid-body .rows');
		const pick_column = async (row, label) => {
			await add_row.click();
			await row.locator('[data-fieldname="fieldname"]').first().click();
			await row.locator('select[data-fieldname="fieldname"]').selectOption(label);
		};

		await pick_column(grid_rows.locator(".grid-row").first(), "Title");
		await pick_column(grid_rows.locator('.grid-row[data-idx="2"]'), "Public");
		await pick_column(grid_rows.locator(".grid-row").last(), "Content");

		await desk.save();

		await page.goto("/note");
		await expect(page).toHaveURL(/\/note\/list/);
		await expect(list_header(page, "Sr.")).toBeAttached();
		await expect(list_header(page, "Title")).toBeAttached();
		await expect(list_header(page, "Public")).toBeAttached();
		await expect(list_header(page, "Content")).toBeAttached();
	});

	test("Breadcrumbs", async ({ page }) => {
		await open_last_list_row(page);

		await expect(first_breadcrumb(page)).toContainText("Note");
		await first_breadcrumb(page).click();
		await expect(page).toHaveURL(/\/note\/list/);
	});

	test("Custom Breadcrumbs", async ({ page, desk }) => {
		const breadcrumbs = '[{"label": _("Notes"), "route":"note"}]';
		await open_settings(page, "Customization");

		await desk.fill_field("breadcrumbs", breadcrumbs, "Code");
		await expect.poll(() => page.evaluate(() => cur_frm.doc.breadcrumbs)).toBe(breadcrumbs);
		await page
			.locator(".form-tabs .nav-item .nav-link", { hasText: "Customization" })
			.first()
			.click();
		await desk.save();

		await open_last_list_row(page);
		await expect(first_breadcrumb(page)).toContainText("Notes");
	});

	test("Read Only", async ({ page }) => {
		await open_last_list_row(page);

		await expect(
			page.locator('.frappe-control[data-fieldname="title"] .control-input')
		).toHaveCSS("display", "none");
	});

	test("Edit Mode", async ({ page, desk }) => {
		await open_settings(page);
		await page.locator('input[data-fieldname="allow_edit"]').check();

		await desk.save();

		await open_last_list_row(page);

		await page.locator(".web-form-actions a", { hasText: "Edit" }).first().click();
		await expect(page).toHaveURL(/\/edit/);

		const title = desk.get_field("title");
		await expect(title).toHaveValue("Note 1");

		// typing into an unfocused input starts at the beginning of its value
		await title.focus();
		await title.pressSequentially(" Edited");
		await submit_web_form(page);
		await page.locator(".success-page .edit-button").click();
		await expect(title).toHaveValue("Note 1 Edited");
	});

	test("Retain Saved Value Over Field Default", async ({ page, api }) => {
		await page.goto("/note");
		await set_web_form_field_default(api, "expire_notification_on", "2030-01-01 00:00:00");

		await open_last_list_row(page);

		await page.locator(".web-form-actions a", { hasText: "Edit" }).first().click();
		await expect(page).toHaveURL(/\/edit/);

		await page.locator('input[data-fieldname="public"]').check();
		await submit_web_form(page);
		await page.locator(".success-page .edit-button").click();

		await expect(page.locator('input[data-fieldname="public"]')).toBeChecked();

		const r = await api.call("frappe.client.get_value", {
			doctype: "Note",
			filters: { title: "Note 1 Edited" },
			fieldname: "expire_notification_on",
		});
		expect(r.message.expire_notification_on).toBeNull();

		await set_web_form_field_default(api, "expire_notification_on", "");
	});

	test("Allow Multiple Response", async ({ page, desk }) => {
		await open_settings(page);
		await page.locator('input[data-fieldname="allow_multiple"]').check();

		await desk.save();

		await page.goto("/note");
		await expect(page).toHaveURL(/\/note\/list/);

		await page.locator(".web-list-actions a:visible", { hasText: "New" }).first().click();
		await expect(page).toHaveURL(/\/note\/new/);

		await desk.fill_field("title", "Note 2");
		await submit_web_form(page);
	});

	test("Allow Delete", async ({ page, desk }) => {
		await open_settings(page);
		await page.locator('input[data-fieldname="allow_delete"]').check();

		await desk.save();

		await page.goto("/note");
		await expect(page).toHaveURL(/\/note\/list/);

		const delete_button = page.locator(".web-list-actions button", { hasText: "Delete" });
		await page
			.locator(".web-list-table tbody tr:nth-child(1) .list-col-checkbox input")
			.click();
		await page
			.locator(".web-list-table tbody tr:nth-child(2) .list-col-checkbox input")
			.click();
		await delete_button.first().click();

		await expect(delete_button.first()).toBeHidden();

		await page.goto("/note");
		await expect(page.locator(".web-list-table tbody tr:nth-child(1)")).toHaveCount(0);
	});

	test("Load Defaults of Fields Without Fieldname", async ({ page, api }) => {
		await set_web_form_fields_without_fieldname(api, [
			{ fieldtype: "Currency", label: "Course Fee", default: "750", read_only: 1 },
			{ fieldtype: "Currency", label: "Tax Amount", default: "135", read_only: 1 },
			{ fieldtype: "Phone", label: "Mobile No", default: "+91-9823341234" },
		]);

		const control = (label) => page.locator(".frappe-control", { hasText: label }).first();

		await page.goto("/note/new");
		await expect(control("Course Fee").locator(".control-value")).toContainText("750.00");
		await expect(control("Tax Amount").locator(".control-value")).toContainText("135.00");
		await expect(control("Mobile No").locator(".selected-phone .country")).toHaveText("+91");
		await expect(control("Mobile No").locator("input")).toHaveValue("9823341234");

		await set_web_form_fields_without_fieldname(api, []);
	});

	test("Navigate and Submit a WebForm", async ({ page, desk }) => {
		await page.goto("/update-profile");

		await page.locator(".web-form-actions a", { hasText: "Edit" }).first().click();

		await desk.fill_field("middle_name", "_Test User");

		await page.locator(".web-form-actions .btn-primary").click();
		await expect(page).toHaveURL(/\/me/);
	});

	test("Navigate and Submit a MultiStep WebForm", async ({ page, desk, api }) => {
		await api.call("frappe.tests.ui_test_helpers.update_webform_to_multistep");
		await page.goto("/update-profile-duplicate");

		await page.locator(".web-form-actions a", { hasText: "Edit" }).first().click();

		await desk.fill_field("middle_name", "_Test User");

		await expect(page.locator(".btn-next")).toBeVisible();
		await page.locator(".btn-next").click();

		await expect(page.locator(".btn-previous")).toBeVisible();
		await expect(page.locator(".btn-next")).toBeHidden();

		await page.locator(".web-form-actions .btn-primary").click();
		await expect(page).toHaveURL(/\/me/);
	});
});
