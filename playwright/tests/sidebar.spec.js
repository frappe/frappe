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

async function open_attach(page) {
	const icon = page.locator('.form-sidebar-action[data-action="attachments"]');
	if (await icon.isDisabled()) {
		await page.locator(".add-attachment-btn").click();
	} else {
		await icon.click();
	}
}

async function verify_attachment_visibility(page, desk, document, is_private) {
	await page.goto(`/desk/${document}`);

	await open_attach(page);
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

	await open_attach(page);
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

		await expect(page.locator(".form-attachments")).toBeHidden();
		await attach_file(page, desk, fixture("sample_image.jpg"));
		await expect(
			page.locator('.form-sidebar-action[data-action="attachments"]')
		).toBeDisabled();
		await expect(page.locator(".explore-link")).toBeVisible();
		await expect(page.locator(".show-all-btn")).toBeHidden();

		await attach_file(page, desk, null, 10);
		await expect(page.locator(".show-all-btn")).toBeVisible();

		await attach_file(page, desk, fixture("sample_attachments/attachment-11.txt"));
		await page.locator(".layout-side-section:visible").evaluate((el) => el.scrollTo(0, 0));
		await expect(page.locator(".add-attachment-btn")).toBeHidden();

		const first_row = page.locator(".form-attachments .attachment-row").first();
		const file_name = (await first_row.locator(".attachment-file-label").innerText()).trim();
		await first_row.locator(".attachment-actions").click();
		await page.locator(".es-menu__item", { hasText: "Make public" }).click();
		await expect(page.getByText(/is now public/)).toBeVisible();
		await expect(
			page
				.locator(".form-attachments .attachment-row", { hasText: file_name })
				.locator(".attachment-icon")
		).toHaveAttribute("title", "Public");
		const files = await api.get_list(
			"File",
			["is_private"],
			[
				["attached_to_name", "=", todo.message.name],
				["file_name", "=", file_name],
			]
		);
		expect(files.data.map((f) => f.is_private)).toEqual([0]);

		await expect(page.locator(".form-attachments .attachment-row")).toHaveCount(3);
		await expect(page.locator(".show-all-btn")).toContainText("9 more");
		await page.locator(".show-all-btn").click();
		const list = page.locator(".attachments-dialog-list .attachment-row");
		await expect(list).toHaveCount(12);
		await page
			.locator(".attachments-dialog input[data-fieldname='search']")
			.fill("attachment-1");
		await expect(list).toHaveCount(3);

		await page.locator(".attachments-select-all input").check();
		await expect(page.locator(".attachments-selection-label")).toHaveText("3 selected");
		await page.locator(".attachments-delete-selected").click();
		await desk.get_open_dialog().getByRole("button", { name: "Yes", exact: true }).click();
		await page.locator(".attachments-dialog input[data-fieldname='search']").fill("");
		await expect(list).toHaveCount(9);
	});

	test("A reader who can't edit a document gets no attach, tag or share buttons", async ({
		browser,
		admin,
		baseURL,
	}) => {
		const reader = "sidebar-reader@example.com";
		const password = "Sidebar Reader 7#qT";
		await admin.insert_doc(
			"User",
			{
				email: reader,
				first_name: "Sidebar Reader",
				new_password: password,
				send_welcome_email: 0,
				roles: [{ role: "Blogger" }],
			},
			true
		);
		// Desk Users read public Notes but edit only their own
		const note = await admin.insert_doc("Note", { title: "Sidebar reader note", public: 1 });

		const context = await browser.newContext({ baseURL, storageState: undefined });
		const page = await context.newPage();
		const res = await page.request.post("/api/method/login", {
			data: { usr: reader, pwd: password },
		});
		expect(res.status()).toBe(200);
		await page.goto(`/desk/note/${note.name}`);

		const action = (key) => page.locator(`.form-sidebar-action[data-action="${key}"]`);
		await expect(action("assign")).toBeVisible();
		for (const key of ["attachments", "tags", "share"]) {
			await expect(action(key)).toBeHidden();
		}
		await context.close();
	});

	test("Add a tag from the combobox and remove it", async ({ page, api }) => {
		const todo = await api.call("frappe.tests.ui_test_helpers.create_todo", {
			description: "Sidebar Tag ToDo",
		});
		await page.goto(`/desk/todo/${todo.message.name}`);
		// a new name each run, so the combobox offers to create it
		const name = `pw-tag-${Date.now()}`;
		const tags = page.locator(".form-tags");
		const tag = tags.locator(".es-tag", { hasText: name });

		await expect(tags).toBeHidden();
		await page.locator('.form-sidebar-action[data-action="tags"]').click();
		const input = page.locator(".es-combobox [role='combobox']");
		await expect(input).toBeFocused();
		await input.fill(name);
		await expect(page.locator(".es-combobox [role='option']").last()).toHaveText(
			`Create tag "${name}"`
		);
		await input.press("Enter");
		await expect(tag).toBeVisible();
		await page.reload();
		await expect(tag).toBeVisible();

		// the same tag in other letter case is not offered again
		await page.locator(".form-tags .add-tags-btn").click();
		await input.fill(name.toUpperCase());
		await expect(page.locator(".es-combobox [role='option']")).toHaveCount(0);
		await input.press("Escape");

		await tag.getByRole("button", { name: `Remove ${name}` }).click();
		await expect(tag).toHaveCount(0);
		await expect(tags).toBeHidden();

		await page.reload();
		await expect(page.locator('.form-sidebar-action[data-action="tags"]')).toBeEnabled();
		await expect(tag).toHaveCount(0);
	});
});
