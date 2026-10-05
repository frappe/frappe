import path from "path";
import { test, expect, use_shared_page } from "../support";
import { drop_file } from "../support/drop_file";

// the page title is the last breadcrumb
const TITLE = ".navbar-breadcrumbs:visible li:last-child";
const WEB_LINK = "https://wallpaperplay.com/walls/full/8/2/b/72402.jpg";
const ATTACHED_FILE_LINK = ".attached-file > .ellipsis > .attached-file-link";

const wait_for_upload = (page) =>
	page.waitForResponse(
		(res) => res.request().method() === "POST" && res.url().includes("/api/method/upload_file")
	);

const wait_for_save = (page) =>
	page.waitForResponse(
		(res) =>
			res.request().method() === "POST" &&
			res.url().includes("/api/method/frappe.desk.form.save.savedocs")
	);

async function upload(page) {
	const uploaded = wait_for_upload(page);
	await page
		.locator(".modal-footer:visible")
		.getByRole("button", { name: "Upload", exact: true })
		.click();
	await uploaded;
}

async function attach_web_link(page) {
	await page.getByRole("button", { name: "Attach", exact: true }).click();
	await page.getByRole("button", { name: "Link", exact: true }).click();
	await page.getByPlaceholder("Attach a web link", { exact: true }).fill(WEB_LINK);
	await upload(page);
	await expect.poll(() => page.evaluate(() => cur_frm.doc.attach)).toBe(WEB_LINK);
}

async function delete_latest_documents(page, desk, count) {
	await desk.go_to_list("Test Attach Control");
	for (let row = 0; row < count; row++) {
		await page.locator(".list-row-checkbox").nth(row).click();
	}
	await desk.click_action_button("Delete");
	const deleted = page.waitForResponse((res) =>
		res.url().includes("/api/method/frappe.desk.reportview.delete_items")
	);
	await desk.click_modal_primary_button("Delete");
	await deleted;
}

test.describe("Attach Control", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_doctype", {
			name: "Test Attach Control",
			fields: [
				{
					label: "Attach File or Image",
					fieldname: "attach",
					fieldtype: "Attach",
					in_list_view: 1,
				},
			],
		});
	});

	test('Checking functionality for "Link" button in the "Attach" fieldtype', async ({
		page,
		desk,
	}) => {
		await desk.new_form("Test Attach Control");

		await attach_web_link(page);
		await desk.save();

		await expect(page.locator(ATTACHED_FILE_LINK)).toHaveAttribute("href", WEB_LINK);

		await page.locator('[data-action="clear_attachment"]').click();

		await expect(page.locator(".control-input > .btn-sm")).toContainText("Attach");

		await delete_latest_documents(page, desk, 1);
	});

	test('Checking functionality for "Library" button in the "Attach" fieldtype', async ({
		page,
		desk,
	}) => {
		await desk.new_form("Test Attach Control");

		await attach_web_link(page);
		await desk.save();

		await desk.new_form("Test Attach Control");

		await page.getByRole("button", { name: "Attach", exact: true }).click();

		await page.getByRole("button", { name: "Library", exact: true }).click();
		await desk.get_open_dialog().getByText("72402.jpg").first().click();

		await upload(page);
		await expect.poll(() => page.evaluate(() => cur_frm.doc.attach)).toBe(WEB_LINK);
		await desk.save();

		await expect(page.locator(ATTACHED_FILE_LINK)).toHaveAttribute("href", WEB_LINK);

		await page.locator('[data-action="clear_attachment"]').click();

		await expect(page.locator(".control-input > .btn-sm")).toContainText("Attach");

		await delete_latest_documents(page, desk, 2);
	});

	test('Checking that "Camera" button in the "Attach" fieldtype does show if camera is available', async ({
		page,
		desk,
	}) => {
		await page.addInitScript(() => {
			Object.defineProperty(navigator, "mediaDevices", {
				value: { ondevicechange: null },
				configurable: true,
			});
		});
		await desk.new_form("Test Attach Control");

		await page.getByRole("button", { name: "Attach", exact: true }).click();

		await expect(page.getByRole("button", { name: "Camera", exact: true })).toBeAttached();
	});

	test('Checking that "Camera" button in the "Attach" fieldtype does not show if no camera is available', async ({
		page,
		desk,
	}) => {
		await page.addInitScript(() => {
			delete Navigator.prototype.mediaDevices;
		});
		await desk.new_form("Test Attach Control");

		await page.getByRole("button", { name: "Attach", exact: true }).click();
		await expect(page.getByRole("button", { name: "Link", exact: true })).toBeVisible();

		await expect(page.getByRole("button", { name: "Camera", exact: true })).toHaveCount(0);
	});
});

test.describe("Attach Control with Failed Document Save", () => {
	const shared = use_shared_page();
	let temp_name = "";
	let docname = "";

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_doctype", {
			name: "Test Mandatory Attach Control",
			fields: [
				{
					label: "Attach File or Image",
					fieldname: "attach",
					fieldtype: "Attach",
					in_list_view: 1,
				},
				{
					label: "Mandatory Text Field",
					fieldname: "text_field",
					fieldtype: "Text Editor",
					in_list_view: 1,
					reqd: 1,
				},
			],
		});
	});

	test("Attaching a file on an unsaved document", async () => {
		const { page, desk } = shared;
		await desk.new_form("Test Mandatory Attach Control");
		const body = page.locator("body");
		temp_name = (await body.getAttribute("data-route")).split("/")[2];

		await attach_web_link(page);

		// uploading on a new doc should not trigger save/validation
		await expect(page.locator(".msgprint-dialog")).toHaveCount(0);

		await expect(page.locator(ATTACHED_FILE_LINK)).toHaveAttribute("href", WEB_LINK);

		await desk.fill_field("text_field", "Random value", "Text Editor");
		await expect
			.poll(() => page.evaluate(() => cur_frm.doc.text_field))
			.toContain("Random value");
		await desk.save();
		await expect(body).not.toHaveAttribute("data-route", new RegExp(temp_name));

		docname = (await page.locator(TITLE).innerText()).trim();
	});

	test("Check if file was uploaded correctly", async () => {
		const { page, desk, api } = shared;

		// the list restores the filters an earlier run left in the user's list settings
		await api.call("frappe.model.utils.user_settings.save", {
			doctype: "File",
			user_settings: JSON.stringify({ File: { filters: [] } }),
		});
		await desk.go_to_list("File");
		await desk.open_list_filter();
		await page.locator(".filter-popover .add-filter").click();
		await desk.pick_filter_field("Attached To Name");
		const attached_to_name = page.locator('input[data-fieldname="attached_to_name"]');
		await attached_to_name.click();
		await attached_to_name.pressSequentially(docname);
		await attached_to_name.blur();
		await page.locator(".filter-popover .add-filter").click();
		await desk.pick_filter_field("Attached To DocType");
		const attached_to_doctype = page
			.locator('input[data-fieldname="attached_to_doctype"]')
			.last();
		await attached_to_doctype.click();
		await attached_to_doctype.pressSequentially("Test Mandatory Attach Control");
		await attached_to_doctype.blur();
		await expect(page.locator("header .level-right .list-count:visible")).toContainText(
			"1 of 1"
		);
	});

	test("Check if file exists with temporary name", async () => {
		const { page, desk } = shared;
		await desk.open_list_filter();
		const attached_to_name = page.locator('input[data-fieldname="attached_to_name"]');
		await attached_to_name.click();
		await attached_to_name.clear();
		await attached_to_name.pressSequentially(temp_name);
		await attached_to_name.blur();
		await expect(page.locator(".frappe-list > .no-result")).toBeVisible();
	});
});

test.describe("Attach Control in a Child Table Row", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_child_doctype", {
			name: "Child Test Attach Control",
			fields: [
				{
					label: "Title",
					fieldname: "title",
					fieldtype: "Data",
					in_list_view: 1,
				},
				{
					label: "Attach File or Image",
					fieldname: "attach",
					fieldtype: "Attach",
				},
			],
		});
		await admin.call("frappe.tests.ui_test_helpers.create_doctype", {
			name: "Test Attach Control Grid",
			fields: [
				{
					label: "Items",
					fieldname: "items",
					fieldtype: "Table",
					options: "Child Test Attach Control",
				},
			],
		});
	});

	test("keeps the row open after uploading and clearing a file", async ({ page, desk }) => {
		await desk.new_form("Test Attach Control Grid");
		const table = page.locator('.frappe-control[data-fieldname="items"]');
		const open_row = page.locator(".grid-row-open");
		await table.getByRole("button", { name: "Add row", exact: true }).click();
		await desk.save();

		await table.locator('[data-idx="1"] .btn-open-row').click();
		await open_row.getByRole("button", { name: "Attach", exact: true }).click();
		// a dialog asked to close while still fading in stays open, covering the row
		await expect(desk.get_open_dialog().locator(".modal-dialog")).toHaveCSS(
			"transform",
			"none"
		);
		await drop_file(
			desk.get_open_dialog().locator(".file-upload-area"),
			path.join(__dirname, "../fixtures/sample_attachments/attachment-2.txt"),
			"text/plain"
		);
		let saved = wait_for_save(page);
		await desk.get_open_dialog().getByRole("button", { name: "Upload", exact: true }).click();
		await saved;

		await expect(open_row).toHaveAttribute("data-idx", "1");
		await expect(open_row.locator(".attached-file-link")).toContainText("attachment-2.txt");

		await open_row.locator('[data-action="clear_attachment"]').click();
		saved = wait_for_save(page);
		await desk.click_modal_primary_button("Yes");
		await saved;

		await expect(open_row).toHaveAttribute("data-idx", "1");
		await expect(open_row.getByRole("button", { name: "Attach", exact: true })).toBeVisible();
	});
});
