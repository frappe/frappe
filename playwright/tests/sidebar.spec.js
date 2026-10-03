import fs from "fs";
import path from "path";
import { test, expect } from "../support";

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
	await page.goto(`/desk/${document}`);

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

test.describe("Sidebar", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_doctype_for_attachment");
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("Property Setter", "ToDo-main-max_attachments", true);
	});

	test("Verify attachment visibility config", async ({ page, desk, api }) => {
		const todo = await api.call("frappe.tests.ui_test_helpers.create_todo", {
			description: "Sidebar Attachment ToDo",
		});
		await verify_attachment_visibility(page, desk, `todo/${todo.message.name}`, true);
		await verify_attachment_visibility(
			page,
			desk,
			"test-blog-category/_Test Blog Category 2",
			false
		);
	});

	test("Verify attachment accessibility UX", async ({ page, desk, api }) => {
		const todo = await api.call(
			"frappe.tests.ui_test_helpers.create_todo_with_attachment_limit",
			{ description: "Sidebar Attachment Access Test ToDo" }
		);
		await page.goto(`/desk/todo/${todo.message.name}`);

		await attach_file(page, desk, fixture("sample_image.jpg"));
		await expect(page.locator(".explore-link")).toBeVisible();
		await expect(page.locator(".show-all-btn")).toBeHidden();

		await attach_file(page, desk, null, 10);
		await expect(page.locator(".show-all-btn")).toBeVisible();

		await attach_file(page, desk, fixture("sample_attachments/attachment-11.txt"));
		await page.locator(".layout-side-section:visible").evaluate((el) => el.scrollTo(0, 0));
		await expect(page.locator(".add-attachment-btn")).toBeHidden();

		await expect(page.locator(".attachment-row")).toHaveCount(10);
		await page.locator(".show-all-btn").click();
		await expect(page.locator(".attachment-row")).toHaveCount(12);
	});
});
