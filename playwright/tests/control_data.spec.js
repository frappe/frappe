import { test, expect, use_shared_page } from "../support";

const TITLE = ".navbar-breadcrumbs:visible li:last-child";
const has_error = /(^|\s)has-error(\s|$)/;

test.describe("Data Control", () => {
	const shared = use_shared_page();

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_doctype", {
			name: "Test Data Control",
			fields: [
				{
					label: "Name",
					fieldname: "name1",
					fieldtype: "Data",
					options: "Name",
					in_list_view: 1,
					reqd: 1,
				},
				{
					label: "Email-ID",
					fieldname: "email",
					fieldtype: "Data",
					options: "Email",
					in_list_view: 1,
					reqd: 1,
				},
				{
					label: "Phone No.",
					fieldname: "phone",
					fieldtype: "Data",
					options: "Phone",
					in_list_view: 1,
					reqd: 1,
				},
			],
		});
		const existing = await admin.get_list("Test Data Control");
		for (const doc of existing.data) {
			await admin.remove_doc("Test Data Control", doc.name);
		}
	});

	const control = (fieldname) =>
		shared.page.locator(`.frappe-control[data-fieldname="${fieldname}"]`);

	async function fill_field(fieldname, value) {
		await shared.desk.fill_field(fieldname, value, "Data");
		await expect
			.poll(() => shared.page.evaluate((fieldname) => cur_frm.doc[fieldname], fieldname))
			.toBe(value);
	}

	async function expect_message(message) {
		const dialog = shared.desk.get_open_dialog();
		await expect(dialog.locator(".modal-title")).toHaveText("Message");
		await expect(dialog.locator(".msgprint")).toHaveText(message);
		await shared.desk.hide_dialog();
	}

	test("check custom formatters", async () => {
		const { page } = shared;
		await page.goto("/desk/doctype/User");
		await expect(
			page.locator(
				'[data-fieldname="fields"] .grid-row[data-idx="3"] [data-fieldname="fieldtype"] .static-area'
			)
		).toHaveText("Section Break");
	});

	test('Verifying data control by inputting different patterns for "Name" field', async () => {
		const { page, desk } = shared;
		await desk.new_form("Test Data Control");

		await expect(page).toHaveURL(/\/test-data-control\/new-test-data-control/);
		await expect(page.locator(TITLE)).toHaveText("New Test Data Control");
		await expect(control("name1").locator("label")).toHaveClass(/(^|\s)reqd(\s|$)/);
		await expect(control("email").locator("label")).toHaveClass(/(^|\s)reqd(\s|$)/);
		await expect(control("phone").locator("label")).toHaveClass(/(^|\s)reqd(\s|$)/);

		await expect(page.locator('[data-testid="page-status"]')).toContainText("Not Saved");

		await fill_field("name1", "@@###");
		await fill_field("email", "test@example.com");
		await fill_field("phone", "9834280031");

		await expect(control("name1")).toHaveClass(has_error);
		await desk.save();
		await expect_message("@@### is not a valid Name");

		await desk.get_field("name1", "Data").clear();
		await fill_field("name1", "Komal{}/!");
		await expect(control("name1")).toHaveClass(has_error);
		await desk.save();
		await expect_message("Komal{}/! is not a valid Name");
	});

	test('Verifying data control by inputting different patterns for "Email" field', async () => {
		const { desk } = shared;
		await desk.get_field("name1", "Data").clear();
		await fill_field("name1", "Komal");
		await desk.get_field("email", "Data").clear();
		await fill_field("email", "komal");
		await expect(control("email")).toHaveClass(has_error);
		await desk.save();
		await expect_message("komal is not a valid Email Address");

		await desk.get_field("email", "Data").clear();
		await fill_field("email", "komal@test");
		await expect(control("email")).toHaveClass(has_error);
		await desk.save();
		await expect_message("komal@test is not a valid Email Address");
	});

	test('Verifying data control by inputting different patterns for "Phone" field', async () => {
		const { page, desk } = shared;
		await desk.get_field("email", "Data").clear();
		await fill_field("email", "komal@test.com");
		await desk.get_field("phone", "Data").clear();
		await fill_field("phone", "komal");
		await expect(control("phone")).toHaveClass(has_error);
		await page.getByRole("button", { name: "Save", exact: true }).click();
		await expect_message("komal is not a valid Phone Number");
	});

	test("Inputting correct data and saving the doc", async () => {
		const { page, desk } = shared;
		await desk.get_field("name1", "Data").clear();
		await desk.get_field("email", "Data").clear();
		await desk.get_field("phone", "Data").clear();
		await fill_field("name1", "Komal");
		await fill_field("email", "komal@test.com");
		await fill_field("phone", "9432380001");
		await page.getByRole("button", { name: "Save", exact: true }).click();

		await expect(page).not.toHaveURL(/\/test-data-control\/new-test-data-control/);
		await expect(desk.get_field("name1")).toHaveValue("Komal");
		await expect(desk.get_field("email")).toHaveValue("komal@test.com");
		await expect(desk.get_field("phone")).toHaveValue("9432380001");
	});

	test("Deleting the doc", async () => {
		const { page, desk, api } = shared;
		await desk.go_to_list("Test Data Control");
		await page.locator(".list-row-checkbox").nth(0).click();
		await desk.click_action_button("Delete");
		await desk.click_modal_primary_button("Delete");
		await expect
			.poll(async () => (await api.get_list("Test Data Control")).data.length)
			.toBe(0);
	});
});
