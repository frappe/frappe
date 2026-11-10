import { test, expect, TEST_USER } from "../support";
import doctype_with_child_table from "../fixtures/doctype_with_child_table";
import doctype_with_link_and_child_table from "../fixtures/doctype_with_link_and_child_table";
import child_table_doctype from "../fixtures/child_table_doctype";
import child_table_doctype_1 from "../fixtures/child_table_doctype_1";
import doctype_to_link from "../fixtures/doctype_to_link";

const doctype_to_link_name = doctype_to_link.name;
const child_table_doctype_name = child_table_doctype.name;
const doctype_with_link_name = doctype_with_link_and_child_table.name;

test.describe("Dashboard links", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", child_table_doctype, true);
		await admin.insert_doc("DocType", child_table_doctype_1, true);
		await admin.insert_doc("DocType", doctype_with_child_table, true);
		await admin.insert_doc("DocType", doctype_with_link_and_child_table, true);
		await admin.insert_doc("DocType", doctype_to_link, true);
		await admin.call("frappe.tests.ui_test_helpers.update_child_table", {
			name: child_table_doctype_name,
		});
		await admin.call("frappe.tests.ui_test_helpers.add_link_field_and_dashboard_link", {
			name: doctype_with_link_name,
		});

		const stale_contacts = await admin.get_list(
			"Contact",
			["name"],
			[
				["first_name", "=", "Admin"],
				["user", "=", TEST_USER],
			]
		);
		for (const contact of stale_contacts.data) {
			await admin.remove_doc("Contact", contact.name, true);
		}
		await admin.remove_doc(doctype_to_link_name, "Test Linking", true);
		await admin.remove_doc(doctype_to_link_name, "Test Parent Linking", true);
	});

	test.beforeEach(async ({ desk }) => {
		await desk.login("Administrator");
	});

	test("Adding a new contact, checking for the counter on the dashboard and deleting the created contact", async ({
		page,
		desk,
	}) => {
		const contact_link = page.locator('.page-container:visible [data-doctype="Contact"]');

		await page.goto("/desk/contact");
		await desk.clear_filters();

		await page.goto(`/desk/user/${TEST_USER}`);

		await desk.select_form_tab("Connections");
		await expect(contact_link.filter({ hasText: "Contact" }).first()).toBeVisible();

		await page.locator('.document-link-badge[data-doctype="Contact"]').click();
		const add_contact = page.getByRole("button", { name: "Add Contact", exact: true });
		await expect(add_contact).toBeVisible();
		await add_contact.click();
		await page
			.locator('[data-doctype="Contact"][data-fieldname="first_name"]')
			.pressSequentially("Admin");
		const saved = page.waitForResponse((res) =>
			res.url().includes("/api/method/frappe.client.save")
		);
		await page.getByRole("button", { name: "Save", exact: true }).click();
		expect((await saved).status()).toBe(200);
		await page.goto(`/desk/user/${TEST_USER}`);

		await desk.select_form_tab("Connections");
		await expect(page.locator('[data-doctype="Contact"] > .count:visible')).toContainText("2");
		await contact_link.getByText("Contact").first().click();

		await page.goto("/desk/contact");
		await expect(desk.listview_row_items.nth(0)).toContainText("Admin");
		await page.locator(".list-subject > .select-like > .list-row-checkbox").nth(0).click();
		await desk.click_action_button("Delete");
		const deleted = page.waitForResponse((res) =>
			res.url().includes("/api/method/frappe.desk.reportview.delete_items")
		);
		await page.getByRole("button", { name: "Delete", exact: true }).click();
		expect((await deleted).status()).toBe(200);

		await page.goto("/desk/user");
		await page.locator(".list-row-col > .level-item > .ellipsis").nth(0).click();
		await expect(contact_link.filter({ hasText: "Contact" }).first()).toBeAttached();
	});

	test("Report link in dashboard", async ({ page, desk }) => {
		await page.goto(`/desk/user/${TEST_USER}`);
		await desk.select_form_tab("Connections");
		await expect(
			page.locator('.document-link[data-doctype="Contact"]').getByText("Contact").first()
		).toBeVisible();
		await page.evaluate(() => {
			cur_frm.dashboard.data.reports = [
				{
					label: "Reports",
					items: ["Website Analytics"],
				},
			];
			cur_frm.dashboard.render_report_links();
		});
		await page
			.locator('.document-link[data-report="Website Analytics"]')
			.getByText("Website Analytics")
			.first()
			.click();
	});

	test("check if child table is populated with linked field on creation from dashboard link", async ({
		page,
		desk,
	}) => {
		await desk.new_form(doctype_to_link_name);
		await desk.fill_field("title", "Test Linking");
		await expect.poll(() => page.evaluate(() => cur_frm.doc.title)).toBe("Test Linking");
		await page.getByRole("button", { name: "Save", exact: true }).click();

		await page.locator('.btn-new[data-doctype="Doctype With Child Table"]').click();
		await expect(
			page.locator(
				'.frappe-control[data-fieldname="child_table"] .rows .data-row .col[data-fieldname="doctype_to_link"]'
			)
		).toContainText("Test Linking");
	});

	test("check if child table is left empty when the link field is on the parent", async ({
		page,
		desk,
	}) => {
		await desk.new_form(doctype_to_link_name);
		await desk.fill_field("title", "Test Parent Linking");
		await expect
			.poll(() => page.evaluate(() => cur_frm.doc.title))
			.toBe("Test Parent Linking");
		await page.getByRole("button", { name: "Save", exact: true }).click();

		await page.locator(`.btn-new[data-doctype="${doctype_with_link_name}"]`).click();

		await expect
			.poll(() =>
				page.evaluate(() => {
					const doc = cur_frm.doc;
					const child_row = doc.child_table?.[0];
					return {
						doctype: doc.doctype,
						doctype_to_link: doc.doctype_to_link,
						has_child_row: Boolean(child_row),
						child_row_is_linked: child_row?.doctype_to_link === "Test Parent Linking",
					};
				})
			)
			.toEqual({
				doctype: doctype_with_link_name,
				doctype_to_link: "Test Parent Linking",
				has_child_row: true,
				child_row_is_linked: false,
			});
	});
});
