import fs from "fs";
import path from "path";
import { test, expect, TEST_USER } from "../support";

const fixture = (file) => path.join(__dirname, "../fixtures", file);

async function drop_files(page, target, files) {
	const payload = files.map((file) => ({
		name: path.basename(file),
		type: file.endsWith(".jpg") ? "image/jpeg" : "text/plain",
		content: fs.readFileSync(file).toString("base64"),
	}));
	const data_transfer = await page.evaluateHandle((payload) => {
		const data_transfer = new DataTransfer();
		for (const { name, type, content } of payload) {
			const bytes = Uint8Array.from(atob(content), (char) => char.charCodeAt(0));
			data_transfer.items.add(new File([bytes], name, { type }));
		}
		return data_transfer;
	}, payload);
	await target.dispatchEvent("drop", { dataTransfer: data_transfer });
}

async function verify_attachment_visibility(page, desk, document, is_private) {
	await page.goto(`/app/${document}`);

	await page.locator(".add-attachment-btn").click();
	await drop_files(page, desk.get_open_dialog().locator(".file-upload-area"), [
		fixture("sample_image.jpg"),
	]);

	const private_checkbox = desk
		.get_open_dialog()
		.getByRole("checkbox", { name: "Private", exact: true });
	if (is_private) {
		await expect(private_checkbox).toBeChecked();
	} else {
		await expect(private_checkbox).not.toBeChecked();
	}
}

async function attach_file(page, desk, file, no_of_files = 1) {
	let files = [];
	if (file) {
		files = [file];
	} else if (no_of_files > 1) {
		files = [...Array(no_of_files)].map((el, idx) =>
			fixture(`sample_attachments/attachment-${idx + 1}${idx == 0 ? ".jpg" : ".txt"}`)
		);
	}

	await page.locator(".add-attachment-btn").click();
	await drop_files(page, desk.get_open_dialog().locator(".file-upload-area"), files);
	await desk.get_open_dialog().getByRole("button", { name: "Upload", exact: true }).click();
}

async function remove_assignments(admin) {
	const assigned = await admin.get_list(
		"ToDo",
		["name"],
		[["_assign", "like", `%${TEST_USER}%`]]
	);
	for (const { name } of assigned.data) {
		await admin.call("frappe.desk.form.assign_to.remove", {
			doctype: "ToDo",
			name,
			assign_to: TEST_USER,
		});
	}
}

test.describe("Sidebar", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_blog_post");
		await remove_assignments(admin);
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("Property Setter", "ToDo-main-max_attachments", true);
		await remove_assignments(admin);
	});

	test("Verify attachment visibility config", async ({ page, desk, api }) => {
		const todo = await api.call("frappe.tests.ui_test_helpers.create_todo", {
			description: "Sidebar Attachment ToDo",
		});
		await verify_attachment_visibility(page, desk, `todo/${todo.message.name}`, true);
		await verify_attachment_visibility(
			page,
			desk,
			"blog-post/test-blog-attachment-post",
			false
		);
	});

	test("Verify attachment accessibility UX", async ({ page, desk, api }) => {
		const todo = await api.call(
			"frappe.tests.ui_test_helpers.create_todo_with_attachment_limit",
			{ description: "Sidebar Attachment Access Test ToDo" }
		);
		await page.goto(`/app/todo/${todo.message.name}`);

		await attach_file(page, desk, fixture("sample_image.jpg"));
		await expect(page.locator(".explore-link")).toBeVisible();
		await expect(page.locator(".show-all-btn")).toBeHidden();

		await attach_file(page, desk, null, 10);
		await expect(page.locator(".show-all-btn")).toBeVisible();

		await attach_file(page, desk, fixture("sample_attachments/attachment-11.txt"));
		await expect(page.locator(".add-attachment-btn")).toBeHidden();
		await expect(page.locator(".explore-link")).toBeVisible();

		await expect(page.locator(".attachment-row")).toHaveCount(10);
		await page.locator(".show-all-btn").click();
		await expect(page.locator(".attachment-row")).toHaveCount(12);
	});

	test('Test for checking "Assigned To" counter value, adding filter and adding & removing an assignment', async ({
		page,
		desk,
		api,
	}) => {
		const todo = await api.call("frappe.tests.ui_test_helpers.create_todo", {
			description: "Sidebar Attachment ToDo",
		});
		const todo_name = todo.message.name;
		const assigned_to = page
			.locator(".list-group-by-fields .list-link > a")
			.filter({ hasText: "Assigned To" });
		const group_by_items = page.locator(
			".group-by-field.show > .dropdown-menu > .group-by-item > .dropdown-item"
		);

		await page.goto("/app/todo");
		await assigned_to.click();
		await expect(page.locator(".group-by-field.show .empty-state")).toContainText(
			"No filters found"
		);

		await page.goto(`/app/todo/${todo_name}`);
		await page.locator(".add-assignment-btn").click();
		await desk.get_field("assign_to_me", "Check").click();
		await expect
			.poll(() => page.evaluate(() => cur_dialog.get_value("assign_to")))
			.toEqual([TEST_USER]);
		const assigned = page.waitForResponse((res) =>
			res.url().includes("/api/method/frappe.desk.form.assign_to.add")
		);
		await page.locator(".modal-footer > .standard-actions > .btn-primary:visible").click();
		await assigned;

		await page.goto("/app/todo");
		await assigned_to.click();
		await expect(group_by_items).toContainText("1");

		await expect(page.locator(".filter-button")).toContainText("Filter");

		const filtered = page.waitForResponse((res) =>
			res.url().endsWith("/api/method/frappe.desk.reportview.get")
		);
		await group_by_items.click();
		await filtered;

		await page.locator(".filter-button").click();
		await expect(page.locator(".filter-label")).toContainText("1");
		await expect(
			page.locator(".fieldname-select-area > .awesomplete > .form-control")
		).toHaveValue("Assigned To");
		await expect(page.locator(".condition")).toHaveValue("like");
		await expect(
			page.locator(".filter-field > .form-group > .input-with-feedback")
		).toHaveValue(`%${TEST_USER}%`);
		await expect(page.locator(".filter-popover")).toHaveCSS("opacity", "1");
		await page.locator(".filter-button").click();
		await expect(page.locator(".filter-popover")).toBeHidden();

		await desk.clear_filters();

		await page.goto(`/app/todo/${todo_name}`);
		await page.locator(".assignments > .avatar-group > .avatar > .avatar-frame").click();
		const removed = page.waitForResponse((res) =>
			res.url().includes("/api/method/frappe.desk.form.assign_to.remove")
		);
		await page.locator(".remove-btn").dispatchEvent("click");
		await removed;
		await desk.hide_dialog();
		await page.goto("/app/todo");
		await assigned_to.click();
		await expect(page.locator(".group-by-field.show .empty-state")).toContainText(
			"No filters found"
		);
	});
});
