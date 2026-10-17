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

	test("Shows linked documents in the sidebar and adds one from the connections dialog", async ({
		page,
		desk,
	}) => {
		const contact_item = page.locator('.form-connections-item[data-doctype="Contact"]');
		const panel = page.locator(".settings-dialog-panel:visible");
		const rows = panel.locator("tr[data-row-idx]");

		await page.goto("/desk/contact");
		await desk.clear_filters();

		await page.goto(`/desk/user/${TEST_USER}`);

		// the sidebar lists the linked contact, the old tab is gone
		await expect(contact_item).toContainText("Contact");
		await expect(
			page.locator(".form-tabs-list [data-toggle='tab']:visible")
		).not.toContainText(["Connections"]);

		// the dialog opens on the clicked doctype
		await contact_item.click();
		await expect(
			page.locator('.settings-dialog-tab-item.active[data-tab-id="Contact"]')
		).toBeVisible();
		await expect(rows.first()).toBeVisible();

		// a new linked contact from the dialog
		await panel.getByRole("button", { name: "New", exact: true }).click();
		await desk
			.get_open_dialog()
			.locator('[data-fieldname="first_name"] input')
			.pressSequentially("Admin");
		const saved = page.waitForResponse((res) =>
			res.url().includes("/api/method/frappe.client.save")
		);
		await desk.get_open_dialog().getByRole("button", { name: "Save", exact: true }).click();
		expect((await saved).status()).toBe(200);

		await page.goto(`/desk/user/${TEST_USER}`);
		await expect(contact_item.locator(".form-connections-count")).toContainText("2");

		// "Open in list view" routes with the link filter
		await page.locator(".form-connections-all").first().click();
		await page.locator('.settings-dialog-tab-item[data-tab-id="Contact"]').click();
		await panel.getByRole("button", { name: "Open in list view" }).click();
		await expect(page).toHaveURL(/\/contact/);

		// a row opens the record
		await page.goto(`/desk/user/${TEST_USER}`);
		await contact_item.click();
		await rows.first().click();
		await expect(page).toHaveURL(/\/contact\/.+/);

		// delete the new contact
		await page.goto("/desk/contact");
		await expect(desk.listview_row_items.nth(0)).toContainText("Admin");
		await page.locator(".list-subject > .select-like > .list-row-checkbox").nth(0).click();
		await desk.click_action_button("Delete");
		const deleted = page.waitForResponse((res) =>
			res.url().includes("/api/method/frappe.desk.reportview.delete_items")
		);
		await page.getByRole("button", { name: "Delete", exact: true }).click();
		expect((await deleted).status()).toBe(200);

		await page.goto(`/desk/user/${TEST_USER}`);
		await expect(contact_item).toBeVisible();
		await expect(contact_item.locator(".form-connections-count")).not.toContainText("2");
	});

	test("connections filter by a link field in a child table, and list nothing when the field is unknown", async ({
		page,
	}) => {
		await page.goto(`/desk/${doctype_to_link_name.toLowerCase().replaceAll(" ", "-")}`);
		const filters = await page.evaluate(async (doctype) => {
			await frappe.model.with_doctype(doctype);
			const dialog = Object.create(frappe.ui.form.ConnectionsDialog.prototype);
			const with_link = (fieldname) => {
				dialog.dashboard = {
					get_link_filters: () => ({ [fieldname]: "Test Linking" }),
					get_link_fieldname: () => fieldname,
				};
				const filters = dialog.get_filters(doctype);
				return filters && dialog.get_list_filters(doctype, filters);
			};
			return { child: with_link("doctype_to_link"), unknown: with_link("no_such_field") };
		}, "Doctype With Child Table");

		expect(filters.child).toEqual([
			["Child Table Doctype", "doctype_to_link", "=", "Test Linking"],
		]);
		expect(filters.unknown).toBeNull();
	});

	test("without counts, connections still list records instead of calling them empty", async ({
		page,
	}) => {
		await page.route("**/frappe.desk.notifications.get_open_count**", (route) =>
			route.fulfill({ status: 500, body: "{}" })
		);
		await page.goto(`/desk/user/${TEST_USER}`);
		const contact_item = page.locator('.form-connections-item[data-doctype="Contact"]');
		await expect(contact_item.locator(".form-connections-count")).toHaveText("");

		await contact_item.click();
		await expect(page.locator(".settings-dialog-panel:visible .connections-empty")).toHaveCount(0);
		await expect(
			page.locator(".settings-dialog-panel:visible tr[data-row-idx]").first()
		).toBeVisible();
	});

	test("Report link in dashboard", async ({ page, desk }) => {
		await page.goto(`/desk/user/${TEST_USER}`);
		await expect(page.locator('.form-connections-item[data-doctype="Contact"]')).toBeVisible();
		// reports have no place in the sidebar, they stay in the dashboard tab
		await page.evaluate(() => {
			cur_frm.dashboard.data.reports = [
				{
					label: "Reports",
					items: ["Website Analytics"],
				},
			];
			cur_frm.refresh();
		});
		await desk.select_form_tab("Connections");
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

		// nothing is linked yet; the dialog is still reachable to make the first one
		await page.locator(".form-connections-all").click();
		await page
			.locator('.settings-dialog-tab-item[data-tab-id="Doctype With Child Table"]')
			.click();
		await expect(page.locator(".connections-empty:visible")).toContainText(
			"No Doctype With Child Table for Test Linking yet"
		);
		await page.locator(".connections-new:visible").click();
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

		await page.locator(".form-connections-all").click();
		await page
			.locator(`.settings-dialog-tab-item[data-tab-id="${doctype_with_link_name}"]`)
			.click();
		await page.locator(".connections-new:visible").click();

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
