import { test, expect } from "../support";

const REPORT_PAGE = "#page-query-report";

async function click_report_menu_item(page, label) {
	await page.locator(`${REPORT_PAGE} .page-actions .menu-btn-group > button`).click();
	await page
		.locator('.es-menu [role="menuitem"]')
		.filter({ hasText: new RegExp(label) })
		.first()
		.click();
}

async function select_autocomplete(desk, fieldname, value) {
	const input = desk
		.get_open_dialog()
		.locator(`.control-input > .awesomplete > input[data-fieldname="${fieldname}"]`);
	await expect(input).toBeVisible();
	await input.clear();
	await input.pressSequentially(value, { delay: 150 });
	await input.press("Enter");
}

async function save_report(page, desk, report_name) {
	await click_report_menu_item(page, "Save");
	await expect(desk.get_open_dialog().locator(".modal-title")).toContainText("Save Report");

	const input = desk.get_open_dialog().locator('input[data-fieldname="report_name"]');
	await input.press("End");
	await input.pressSequentially(report_name, { delay: 100 });
	const saved = page.waitForResponse((res) =>
		res.url().includes("/api/method/frappe.desk.query_report.save_report")
	);
	await desk.get_open_dialog().getByRole("button", { name: "Submit", exact: true }).click();
	await saved;
}

test.describe("Query Report", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc(
			"Report",
			{
				report_name: "Test ToDo Report",
				ref_doctype: "ToDo",
				report_type: "Query Report",
				query: "select * from tabToDo",
			},
			true
		);
		await admin.create_records({
			doctype: "ToDo",
			description: "this is a test todo for query report",
		});
	});

	test("add custom column in report", async ({ page, desk }) => {
		await page.goto("/desk/query-report/Permitted Documents For User");

		await expect(page.locator(".page-form.flex")).toHaveCount(1, { timeout: 60000 });

		// set each filter in one go: typing it out makes the report run with partial values
		const input_user = page.locator(`${REPORT_PAGE} input[data-fieldname="user"]`);
		await input_user.fill("test@erpnext.com");
		await input_user.blur();
		const input_role = page.locator(`${REPORT_PAGE} input[data-fieldname="doctype"]`);
		await input_role.fill("Role");
		await input_role.blur();

		await expect(page.locator(".datatable")).toBeAttached();
		await click_report_menu_item(page, "Add Column");
		await expect(desk.get_open_dialog().locator(".modal-title")).toContainText("Add Column");
		await desk
			.get_open_dialog()
			.locator('select[data-fieldname="doctype"]')
			.selectOption("Role (Name)");
		await select_autocomplete(desk, "field", "Role Name");
		await select_autocomplete(desk, "insert_after", "Name");
		await desk.get_open_dialog().getByRole("button", { name: "Submit", exact: true }).click();

		await save_report(page, desk, "Test Report");
	});

	test("requires document type and field before adding a custom column", async ({
		page,
		desk,
	}) => {
		await page.goto("/desk/query-report/Test ToDo Report");

		await expect(page.locator(".datatable")).toBeAttached({ timeout: 60000 });
		await click_report_menu_item(page, "Add Column");
		await expect(desk.get_open_dialog().locator(".modal-title")).toContainText("Add Column");
		await desk.get_open_dialog().getByRole("button", { name: "Submit", exact: true }).click();

		const msgprint = page.locator(".msgprint");
		await expect(msgprint).toBeVisible();
		await expect(msgprint).toContainText("From Document Type");
		await expect(msgprint).toContainText("Field");
	});

	const save_report_and_open = async (page, desk, report, update_name) => {
		await save_report(page, desk, update_name);

		await page.goto("/desk/query-report/" + report);
		await expect(page.locator(".datatable")).toBeAttached();
	};

	test("test multi level query report", async ({ page, desk }) => {
		await page.goto("/desk/query-report/Test ToDo Report");
		await expect(page.locator(".datatable")).toBeAttached();

		await save_report_and_open(page, desk, "Test ToDo Report 1", " 1");
		await save_report_and_open(page, desk, "Test ToDo Report 11", "1");
	});
});
