import { test, expect, use_shared_page } from "../support";

test.describe("MultiSelectDialog", () => {
	const shared = use_shared_page();

	test.beforeAll(async ({ admin }) => {
		const contact_template = {
			doctype: "Contact",
			first_name: "Test",
			status: "Passive",
			email_ids: [
				{
					doctype: "Contact Email",
					email_id: "test@example.com",
					is_primary: 0,
				},
			],
		};
		const existing = await admin.call("frappe.client.get_count", {
			doctype: "Contact",
			filters: { first_name: "Test", status: "Passive" },
		});
		for (let i = existing.message; i < 25; i++) {
			await admin.insert_doc("Contact", contact_template, true);
		}

		await shared.page.goto("/desk");
		await shared.desk.ready();
	});

	function open_multi_select_dialog(page) {
		return page.evaluate(() => {
			new frappe.ui.form.MultiSelectDialog({
				doctype: "Contact",
				target: {},
				setters: {
					status: null,
					gender: null,
				},
				add_filters_group: 1,
				allow_child_item_selection: 1,
				child_fieldname: "email_ids",
				child_columns: ["email_id", "is_primary"],
			});
		});
	}

	const control = (fieldname) =>
		shared.desk.get_open_dialog().locator(`.frappe-control[data-fieldname="${fieldname}"]`);
	const rows = () => shared.desk.get_open_dialog().locator(".datatable .dt-scrollable .dt-row");

	test("checks multi select dialog api works", async () => {
		await open_multi_select_dialog(shared.page);
		await expect(shared.desk.get_open_dialog()).toContainText("Select Contact");
	});

	test("checks for filters", async () => {
		for (const fieldname of ["search_term", "status", "gender"]) {
			await expect(control(fieldname)).toBeAttached();
		}

		await expect(control("filter_area")).toBeAttached();
	});

	test("checks for child item selection", async () => {
		const row_header = shared.desk.get_open_dialog().locator(".dt-row-header");
		await expect(row_header).toHaveCount(0);

		const checkbox = control("allow_child_item_selection").locator(
			'input[data-fieldname="allow_child_item_selection"]'
		);
		await expect(checkbox).toBeAttached();
		await checkbox.click();

		await expect(control("child_selection_area")).toBeAttached();

		await expect(row_header).toContainText("Contact");
		await expect(row_header).toContainText("Email Id");
		await expect(row_header).toContainText("Is Primary");
	});

	test("tests more button", async () => {
		const search_term = control("search_term").locator('input[data-fieldname="search_term"]');
		await expect(search_term).toBeAttached();
		await search_term.pressSequentially("Test", { delay: 200 });
		const more_btn = control("more_child_btn");
		await expect(more_btn).toBeAttached();

		await expect(rows()).toHaveCount(20);

		const more_records = shared.page.waitForResponse(
			(res) =>
				res.request().method() === "POST" &&
				res.url().includes("api/method/frappe.client.get_list")
		);
		await more_btn.locator("button").click();
		await more_records;

		await expect.poll(() => rows().count(), "More button doesn't work").toBeGreaterThan(20);
	});

	test("scopes child rows to filtered parents", async () => {
		const search_term = control("search_term").locator('input[data-fieldname="search_term"]');
		await search_term.clear();
		await search_term.pressSequentially("NoSuchContactXYZ", { delay: 200 });

		await expect(rows()).toHaveCount(0);
	});
});
