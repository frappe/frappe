import { test, expect } from "../support";
import { shown_dialog } from "../support/shown_dialog";

test.describe("Dynamic Link", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_doctype", {
			name: "Test Dynamic Link",
			fields: [
				{
					label: "Document Type",
					fieldname: "doc_type",
					fieldtype: "Link",
					options: "DocType",
					in_list_view: 1,
					in_standard_filter: 1,
				},
				{
					label: "Document ID",
					fieldname: "doc_id",
					fieldtype: "Dynamic Link",
					options: "doc_type",
					in_list_view: 1,
					in_standard_filter: 1,
				},
			],
		});
	});

	async function get_dialog_with_dynamic_link(page, desk) {
		await page.goto("/desk/doctype");
		await desk.ready();
		return desk.dialog({
			title: "Dynamic Link",
			fields: [
				{
					label: "Document Type",
					fieldname: "doc_type",
					fieldtype: "Link",
					options: "DocType",
					in_list_view: 1,
				},
				{
					label: "Document ID",
					fieldname: "doc_id",
					fieldtype: "Dynamic Link",
					options: "doc_type",
					in_list_view: 1,
				},
			],
		});
	}

	async function get_dialog_with_dynamic_link_option(page, desk) {
		await page.goto("/desk/doctype");
		await desk.ready();
		const dialog = await page.evaluateHandle(() => {
			const dialog = new frappe.ui.Dialog({
				title: "Dynamic Link",
				fields: [
					{
						label: "Document Type",
						fieldname: "doc_type",
						fieldtype: "Link",
						options: "DocType",
						in_list_view: 1,
					},
					{
						label: "Document ID",
						fieldname: "doc_id",
						fieldtype: "Dynamic Link",
						get_options: () => {
							return "User";
						},
						in_list_view: 1,
					},
				],
			});
			dialog.show();
			return dialog;
		});
		return shown_dialog(dialog);
	}

	async function expect_doc_id_options(page) {
		await expect(
			page.locator('[data-fieldname="doc_id"]:visible .awesomplete div')
		).not.toHaveCount(0);
	}

	test("Creating a dynamic link by passing option as function and verifying it in a dialog", async ({
		page,
		desk,
	}) => {
		await get_dialog_with_dynamic_link_option(page, desk);
		await desk.get_field("doc_type").clear();
		await desk.fill_field("doc_type", "User", "Link");
		await desk.get_field("doc_id").click();

		await expect_doc_id_options(page);
		await page.locator(".btn-modal-close:visible").click();
	});

	test("Creating a dynamic link and verifying it in a dialog", async ({ page, desk }) => {
		await get_dialog_with_dynamic_link(page, desk);
		await desk.get_field("doc_type").clear();
		await desk.fill_field("doc_type", "User", "Link");
		await desk.get_field("doc_id").click();

		await expect_doc_id_options(page);
		await page.locator(".btn-modal-close:visible").click();
	});

	test("Shows dynamic link options in list filters", async ({ page, desk }) => {
		await page.goto("/desk/test-dynamic-link");

		await desk.get_field("doc_type").clear();
		await desk.fill_field("doc_type", "User", "Link");
		await desk.get_field("doc_id").click();

		await expect_doc_id_options(page);
	});

	test("Shows dynamic link options in new form", async ({ page, desk }) => {
		await desk.new_form("Test Dynamic Link");
		await desk.get_field("doc_type").clear();
		await desk.fill_field("doc_type", "User", "Link");

		// the dynamic link's get_options() reads the model value, which is set asynchronously
		// on blur: wait for it to land before opening doc_id
		await expect.poll(() => page.evaluate(() => cur_frm.doc.doc_type)).toBe("User");

		await desk.get_field("doc_id").click();

		await expect_doc_id_options(page);
		await desk.get_field("doc_type").clear();
	});

	test("Shows error when invalid DocType is passed", async ({ page, desk }) => {
		await desk.new_form("Test Dynamic Link");
		await desk.get_field("doc_type").clear();
		await desk.fill_field("doc_type", "System Settings", "Link");

		await expect.poll(() => page.evaluate(() => cur_frm.doc.doc_type)).toBe("System Settings");
		await desk.get_field("doc_id").click();

		await expect(page.locator(".modal-title:visible")).toHaveText("Error");
		await expect(page.locator(".msgprint:visible")).toHaveText(
			"System Settings is not a valid DocType for Dynamic Link"
		);
	});
});
